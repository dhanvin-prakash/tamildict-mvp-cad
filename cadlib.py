"""Shared helpers for the TamilDict assemblies: coloured STEP import, height map, interference
check, assembly STEP export and VTK offscreen rendering. Run with the CadQuery venv."""
import math
import os

import cadquery as cq
import vtk
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool


# ------------------------------------------------------------------ STEP import with colours
def load_step_solids(path, default=(0.25, 0.25, 0.27)):
    """Return [(cq.Solid, (r,g,b))] for every solid; colour from the solid or its first coloured face."""
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    rd = STEPCAFControl_Reader()
    rd.SetColorMode(True)
    if rd.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError(f"cannot read {path}")
    rd.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    kinds = (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen)

    def col(shape):
        c = Quantity_Color()
        for k in kinds:
            if ct.GetColor(shape, k, c):
                return (c.Red(), c.Green(), c.Blue())
        return None

    labels = TDF_LabelSequence()
    st.GetFreeShapes(labels)
    out = []
    for i in range(1, labels.Length() + 1):
        exp = TopExp_Explorer(st.GetShape_s(labels.Value(i)), TopAbs_SOLID)
        while exp.More():
            s = exp.Current()
            c = col(s)
            if c is None:
                fe = TopExp_Explorer(s, TopAbs_FACE)
                while fe.More() and c is None:
                    c = col(fe.Current())
                    fe.Next()
            out.append((cq.Solid(s), c or default))
            exp.Next()
    return out


# ------------------------------------------------------------------ geometry helpers
def bbox_overlap(a, b, pad=0.0):
    return not (a.xmax + pad < b.xmin or b.xmax + pad < a.xmin or a.ymax + pad < b.ymin or
                b.ymax + pad < a.ymin or a.zmax + pad < b.zmin or b.zmax + pad < a.zmin)


_BOX_CACHE = {}


def _boxes(solids):
    key = id(solids)
    if key not in _BOX_CACHE:
        _BOX_CACHE[key] = [(b.xmin, b.xmax, b.ymin, b.ymax, b.zmin) for b in (s.BoundingBox() for s, _ in solids)]
    return _BOX_CACHE[key]


def lowest_under(solids, x0, x1, y0, y1, zcap=0.0):
    """Lowest z of any solid whose footprint overlaps the rectangle (the board hangs downwards)."""
    z = zcap
    for bx0, bx1, by0, by1, bz in _boxes(solids):
        if bx1 > x0 and bx0 < x1 and by1 > y0 and by0 < y1 and bz < z:
            z = bz
    return z


def interference(named_parts, module, tol=1e-3):
    """Exact boolean overlap between each named part and every module solid (bbox-prefiltered),
    and between the named parts themselves. Returns a list of (a, b, volume mm^3)."""
    hits = []
    shapes = [(n, s.val() if isinstance(s, cq.Workplane) else s) for n, s in named_parts]
    mboxes = [m.BoundingBox() for m, _ in module]
    for n, s in shapes:
        bb = s.BoundingBox()
        for i, (m, _) in enumerate(module):
            mb = mboxes[i]
            if not bbox_overlap(bb, mb):
                continue
            v = s.intersect(m).Volume()
            if v > tol:
                hits.append((n, f"module solid #{i} ({mb.xlen:.1f}x{mb.ylen:.1f}x{mb.zlen:.1f} @ "
                                f"{(mb.xmin+mb.xmax)/2:.1f},{(mb.ymin+mb.ymax)/2:.1f},{(mb.zmin+mb.zmax)/2:.1f})", v))
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            a, b = shapes[i][1], shapes[j][1]
            if bbox_overlap(a.BoundingBox(), b.BoundingBox()):
                v = a.intersect(b).Volume()
                if v > tol:
                    hits.append((shapes[i][0], shapes[j][0], v))
    return hits


def sweep_wire(points, d=1.0):
    """Round wire of diameter d along a polyline (rounded corners)."""
    p0, p1 = cq.Vector(*points[0]), cq.Vector(*points[1])
    n = (p1 - p0).normalized()
    ref = cq.Vector(0, 0, 1) if abs(n.z) < 0.9 else cq.Vector(1, 0, 0)
    x = n.cross(ref).normalized()
    path = cq.Workplane("XY").polyline(points)
    return cq.Workplane(cq.Plane(origin=p0, xDir=x, normal=n)).circle(d / 2).sweep(path, transition="round")


def export_assembly(parts, path, name):
    """parts: [(name, shape_or_workplane_or_list_of_solids, (r,g,b))] -> coloured STEP assembly."""
    asm = cq.Assembly(name=name)
    for n, s, c in parts:
        if isinstance(s, list):
            s = cq.Compound.makeCompound(s)
        elif isinstance(s, cq.Workplane):
            s = s.val()
        asm.add(s, name=n, color=cq.Color(*c, 1.0))
    asm.save(path, exportType="STEP")


# ------------------------------------------------------------------ VTK rendering
def to_polydata(shape, tol=0.05, ang=0.2):
    verts, tris = shape.tessellate(tol, ang)
    pts = vtk.vtkPoints()
    for v in verts:
        pts.InsertNextPoint(v.x, v.y, v.z)
    cells = vtk.vtkCellArray()
    for t in tris:
        cells.InsertNextCell(3)
        for i in t:
            cells.InsertCellPoint(i)
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(pd)
    nrm.SetFeatureAngle(35)
    nrm.SplittingOn()
    nrm.ConsistencyOn()
    nrm.Update()
    return nrm.GetOutput()


class Scene:
    def __init__(self, size=(1800, 1350), bg=((0.96, 0.97, 0.98), (0.82, 0.85, 0.88))):
        self.ren = vtk.vtkRenderer()
        self.ren.GradientBackgroundOn()
        self.ren.SetBackground(*bg[1])
        self.ren.SetBackground2(*bg[0])
        self.win = vtk.vtkRenderWindow()
        self.win.SetOffScreenRendering(1)
        self.win.SetSize(*size)
        self.win.AddRenderer(self.ren)
        if os.environ.get("CAD_SIMPLE_GL"):          # headless Mesa in CI: no MSAA / FXAA / SSAO
            self.win.SetMultiSamples(0)
        else:
            self.win.SetMultiSamples(8)
            self.ren.UseFXAAOn()
            try:
                self.ren.UseSSAOOn()
                self.ren.SetSSAORadius(4.0)
                self.ren.SetSSAOKernelSize(128)
            except AttributeError:
                pass
        kit = vtk.vtkLightKit()
        kit.SetKeyLightIntensity(0.95)
        kit.AddLightsToRenderer(self.ren)
        self.groups = {}

    def add(self, group, shape, color, spec=0.25, gloss=20, opacity=1.0, tol=0.05):
        if isinstance(shape, cq.Workplane):
            shape = shape.val()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(to_polydata(shape, tol))
        a = vtk.vtkActor()
        a.SetMapper(mapper)
        p = a.GetProperty()
        p.SetColor(*color)
        p.SetSpecular(spec)
        p.SetSpecularPower(gloss)
        p.SetDiffuse(0.85)
        p.SetAmbient(0.12)
        p.SetOpacity(opacity)
        self.ren.AddActor(a)
        self.groups.setdefault(group, []).append(a)
        return a

    def add_image_plane(self, group, png, origin, p1, p2):
        rd = vtk.vtkPNGReader()
        rd.SetFileName(png)
        tex = vtk.vtkTexture()
        tex.SetInputConnection(rd.GetOutputPort())
        tex.InterpolateOn()
        tex.MipmapOn()
        tex.UseSRGBColorSpaceOn()
        pl = vtk.vtkPlaneSource()
        pl.SetOrigin(*origin)
        pl.SetPoint1(*p1)
        pl.SetPoint2(*p2)
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(pl.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.SetTexture(tex)
        a.GetProperty().LightingOff()
        self.ren.AddActor(a)
        self.groups.setdefault(group, []).append(a)

    def offset(self, group, dx=0, dy=0, dz=0):
        for a in self.groups.get(group, []):
            a.SetPosition(dx, dy, dz)

    def show(self, group, on=True):
        for a in self.groups.get(group, []):
            a.SetVisibility(on)

    def shoot(self, path, pos, focal=(0, 0, 0), up=(0, 1, 0), angle=24, zoom=1.0):
        cam = self.ren.GetActiveCamera()
        cam.SetPosition(*pos)
        cam.SetFocalPoint(*focal)
        cam.SetViewUp(*up)
        cam.SetViewAngle(angle)
        self.ren.ResetCameraClippingRange()
        cam.Zoom(zoom)
        self.win.Render()
        w2i = vtk.vtkWindowToImageFilter()
        w2i.SetInput(self.win)
        w2i.SetInputBufferTypeToRGB()
        w2i.ReadFrontBufferOff()
        w2i.Update()
        wr = vtk.vtkPNGWriter()
        wr.SetFileName(path)
        wr.SetInputConnection(w2i.GetOutputPort())
        wr.Write()


def fit_distance(radius, angle=24, margin=1.15):
    return radius * margin / math.sin(math.radians(angle) / 2)
