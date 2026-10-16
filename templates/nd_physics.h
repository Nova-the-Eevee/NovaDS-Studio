#ifndef ND_PHYSICS_H
#define ND_PHYSICS_H
#include <stdint.h>
typedef struct {
    int32_t x,y;     /* 16.16 pixel coordinates, top-left corner */
    int w,h;         /* width and height in pixels */
} NdPhysRect;
/* Inclusive boundary detection for events; excludes corner-only contacts. */
int nd_physics_touch(NdPhysRect a,NdPhysRect b);
/* Clamp axis target to nearest unpenetrated obstacle. No tunneling. */
int32_t nd_physics_limit(NdPhysRect body,int32_t target,int axis,NdPhysRect wall);
#endif
