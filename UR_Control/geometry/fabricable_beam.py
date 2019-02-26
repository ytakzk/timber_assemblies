"""Provides a scripting component.
    Inputs:
        x: The x script variable
        y: The y script variable
    Output:
        a: The a output variable"""

__author__ = "ytakzk"
__version__ = "2019.02.26"

import Rhino.Geometry as rg
import os
import json
import compas_timber
from compas_timber.beam import Beam, BeamEnd, BeamSide 
from compas_timber.utilities import *
from compas.geometry import Plane
import math

root_path  = ghenv.Component.OnPingDocument().FilePath
root_dir = os.path.dirname(os.path.realpath(root_path))

class FabricableBeam(object):

    def __init__(self, base_plane, dx, dy, dz, holes):
        """
        initialization

        :param gripping_plane: gripping_plane plane to grab the beam
        :param top_plane:  top_plane plane to be drilled
        :param bottom_plane:  bottom_plane plane to be drilled
        :param middle_plane:  middle_plane plane to be drilled
        :param beam_brep: beam brep to be drilled (for debug purpose only)
        """

        # create holes
        
        self.base_plane = base_plane
        self.dx = dx
        self.dy = dy
        self.dz = dz
        
        self.holes = holes
    
    def transform(self, transform):
        
        base_plane = rg.Plane(self.base_plane)
        base_plane.Transform(transform)
        
        holes = []
        
        for h in self.holes:
            
            hole = rg.Plane(h)
            hole.Transform(transform)
            holes.append(hole)
        
        return FabricableBeam(base_plane, \
                self.dx, self.dy, self.dz, holes)
    
    def create_brep(self):
        
        x = rg.Interval(-self.dx * 0.5, self.dx * 0.5)
        y = rg.Interval(-self.dy * 0.5, self.dy * 0.5)
        z = rg.Interval(-self.dz * 0.5, self.dz * 0.5)
        
        return rg.Box(self.base_plane, x, y, z)
    
    def create_compas_beam(self):
        
        start_plane = rg.Plane(self.base_plane)
        start_plane.Translate(self.base_plane.XAxis * self.dx * 0.5)
    
        end_plane = rg.Plane(self.base_plane)
        end_plane.Translate(-self.base_plane.XAxis * self.dx * 0.5)
    
        e1 = BeamEnd(start_plane.Origin)
        e2 = BeamEnd(end_plane.Origin)
        
        normal = ([self.base_plane.ZAxis.X, self.base_plane.ZAxis.Y, self.base_plane.ZAxis.Z])
        
        compas_beam = Beam(e1, e2, b.dy, b.dz, normal)
        
        compas_beam.end1.cut_pln_explicit = Plane(start_plane.Origin, start_plane.XAxis)
        compas_beam.end2.cut_pln_explicit = Plane(end_plane.Origin, -end_plane.XAxis)
        
        return compas_beam
    
    def get_dowel_lines(self, extension=0, dowel_radius=50):

        plane_1 = rg.Plane(self.base_plane)
        plane_1.Translate(self.base_plane.Normal * self.dz * 0.5)

        plane_2 = rg.Plane(self.base_plane)
        plane_2.Translate(-self.base_plane.Normal * self.dz * 0.5)

        lines = []
        
        for hole in self.holes:
                
            # get an infinite line
            DIFF = hole.Normal * 9999
            
            p1 = rg.Point3d.Add(hole.Origin, DIFF)
            p2 = rg.Point3d.Add(hole.Origin, -DIFF)
    
            dowel_line = rg.Line(p1, p2)
            
            succeeded, v1 = rg.Intersect.Intersection.LinePlane(dowel_line, plane_1)
            succeeded, v2 = rg.Intersect.Intersection.LinePlane(dowel_line, plane_2)
            
            p1 = dowel_line.PointAt(v1)
            p2 = dowel_line.PointAt(v2)
            
            line = rg.Line(p1, p2)

            angle = rg.Vector3d.VectorAngle(self.base_plane.Normal, hole.Normal)
            diff = self.dz * 0.5 / math.sin(angle) + abs(dowel_radius / math.tan(angle))
            
            diff = (diff + extension) * 0.5
            
            line.Extend(diff, diff)
            lines.append(line)
        
        return lines
    
    @staticmethod
    def instantiate_from_beam(beam):

        holes = []
        for d in beam.dowel_list:
            
            line = d.get_line(scale_value=1.2)
            
            suceeeded, val = rg.Intersect.Intersection.LinePlane(line, beam.base_plane)
            
            if not suceeeded:
                ValueError('No intersection found')
            
            p = line.PointAt(val)
            
            hole = rg.Plane(d.get_plane())
            hole.Origin = p
            
            holes.append(hole)
        
        return FabricableBeam(beam.base_plane, \
            beam.dx + (beam.extension + beam.end_cover) * 2, beam.dy, beam.dz, holes)
            
    @staticmethod
    def write_as_json(beams, name='name', to='data'):
        
        dir = os.sep.join([root_dir, to])
        if not os.path.exists(dir):
            os.makedirs(dir)
        
        path = os.sep.join([root_dir, to, str(name) + '.json'])
        
        data = []
        
        for b in beams:
            
            d = {
                'plane': FabricableBeam.plane_to_dic(b.base_plane),
                'dx': b.dx,
                'dy': b.dy,
                'dz': b.dz,
            }
            
            d['holes'] = [FabricableBeam.plane_to_dic(h) for h in b.holes]
            
            data.append(d)
        
        with open(path, 'w') as f:  
            json.dump(data, f)

    @staticmethod
    def read_from_json(path):
        
        beams = []
        
        with open(path, 'r') as f:
            data = json.load(f)
            
            for d in data: 
            
                dx = float(d['dx'])
                dy = float(d['dy'])
                dz = float(d['dz'])
                base_plane = FabricableBeam.dic_to_plane(d['plane'])
                holes = [FabricableBeam.dic_to_plane(dic) for dic in d['holes']]
                
                beam = FabricableBeam(base_plane, dx, dy, dz, holes)
                beams.append(beam)
                
        return beams
        
    @staticmethod
    def plane_to_dic(plane):
        
        return {
            'x': plane.Origin.X,
            'y': plane.Origin.Y,
            'z': plane.Origin.Z,
            'xx': plane.XAxis.X,
            'xy': plane.XAxis.Y,
            'xz': plane.XAxis.Z,
            'yx': plane.YAxis.X,
            'yy': plane.YAxis.Y,
            'yz': plane.YAxis.Z
        }
        
    @staticmethod
    def dic_to_plane(dic):

        origin = rg.Point3d(float(dic['x']), float(dic['y']), float(dic['z']))
        xaxis = rg.Vector3d(float(dic['xx']), float(dic['xy']), float(dic['xz']))
        yaxis = rg.Vector3d(float(dic['yx']), float(dic['yy']), float(dic['yz']))

        return rg.Plane(origin, xaxis, yaxis) 
    
    @staticmethod
    def orient_structure(beams, src, target=rg.Plane.WorldXY):
        
        transform = rg.Transform.PlaneToPlane(src, target)
        
        transformed_beams = []
        
        for b in beams:
            
            beam = b.transform(transform)
            transformed_beams.append(beam)
        
        return transformed_beams