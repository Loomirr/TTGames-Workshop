"""Observed original-PC triangle UV derivatives and strip assignment.

The game uses a unit reciprocal for nearly singular UVs. This is deliberately
not MikkTSpace. Strip assignment normalizes each triangle result and overwrites
shared vertex slots; untouched scratch slots remain explicitly unknown.
"""
from shader_reference import vector
import math


def triangle_basis(positions, uvs):
    positions=tuple(vector(p,3,'Triangle position') for p in positions)
    uvs=tuple(vector(uv,2,'Triangle UV') for uv in uvs)
    if len(positions)!=3 or len(uvs)!=3:
        raise ValueError('Tangent calculation requires three positions and UVs')
    edge1=tuple(b-a for a,b in zip(positions[0],positions[1]))
    edge2=tuple(b-a for a,b in zip(positions[0],positions[2]))
    du1,dv1=(b-a for a,b in zip(uvs[0],uvs[1]))
    du2,dv2=(b-a for a,b in zip(uvs[0],uvs[2]))
    determinant=du1*dv2-du2*dv1
    # Exact float constant in the reviewed executable; equality uses fallback.
    reciprocal=1/determinant if abs(determinant)>9.999999747378752e-5 else 1.
    return (vector(((a*dv2-b*dv1)*reciprocal for a,b in zip(edge1,edge2)),3,'Tangent result'),
            vector(((b*du1-a*du2)*reciprocal for a,b in zip(edge1,edge2)),3,'Bitangent result'))


def strip_tangents(positions, uvs, indices):
    """Reviewed strip assignment: last triangle wins, with no normal projection.

    Return None for untouched vertices; the game scratch buffer is not cleared
    here, so inventing an initial value for those vertices would be incorrect.
    """
    positions=tuple(vector(p,3,'Position') for p in positions)
    uvs=tuple(vector(uv,2,'UV') for uv in uvs)
    if len(positions)!=len(uvs) or len(indices)<3:
        raise ValueError('Invalid tangent strip tables')
    if any(type(i) is not int or not 0<=i<len(positions) for i in indices):
        raise ValueError('Tangent strip index outside vertex table')
    result=[None]*len(positions)
    for a,b,c in zip(indices,indices[1:],indices[2:]):
        if a==b or b==c:
            continue
        tangent,_=triangle_basis([positions[i] for i in (a,b,c)],[uvs[i] for i in (a,b,c)])
        length=math.sqrt(sum(v*v for v in tangent))
        tangent=tuple(v/length for v in tangent) if length else (0.,0.,0.)
        for i in (a,b,c):result[i]=tangent
    return result
