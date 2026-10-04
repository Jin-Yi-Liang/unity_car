"""Pixel to local metric XY. No height parameter belongs in this transform."""
import math


class MetricMapping:
    def __init__(self, calibration):
        self.matrix = calibration['pixel_to_metric_matrix']
        a,b,_ = self.matrix[0]; c,d,_ = self.matrix[1]
        self.area_scale = abs(a*d-b*c)
        self.nominal_scale = math.sqrt(self.area_scale)
        if not math.isfinite(self.nominal_scale) or self.nominal_scale <= 0:
            raise ValueError('Singular or non-finite metric mapping')

    def point(self, p):
        a,b,t = self.matrix[0]; c,d,u = self.matrix[1]
        return [a*p[0]+b*p[1]+t, c*p[0]+d*p[1]+u]

    def shapely_coefficients(self):
        a,b,t = self.matrix[0]; c,d,u = self.matrix[1]
        return [a,b,c,d,t,u]

    def distance(self, a, b):
        return math.dist(self.point(a), self.point(b))
