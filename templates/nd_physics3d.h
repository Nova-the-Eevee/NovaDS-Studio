#ifndef ND_PHYSICS3D_H
#define ND_PHYSICS3D_H
#include <stdint.h>
/* Platform-independent 16.16 fixed point, world Y axis points UP. */
typedef struct { int32_t x,y,z,hx,hy,hz; } NdBox3;
int nd3d_touch(NdBox3 a,NdBox3 b);
/* Prevent tunneling into an axis-aligned static box, one axis at a time. */
int32_t nd3d_limit(NdBox3 a,int32_t target,int axis,NdBox3 b);
/* Exact sphere/sphere and sphere/box overlap used for trigger contacts. */
int nd3d_overlap(NdBox3 a,int sphere_a,NdBox3 b,int sphere_b);
#endif
