#include "nd_physics3d.h"
#include <stdint.h>
static int64_t abs64(int64_t n){return n<0?-n:n;}
static int64_t clamp64(int64_t v,int64_t lo,int64_t hi){return v<lo?lo:(v>hi?hi:v);}
static int overlap_axis(int64_t x,int64_t hx,int64_t y,int64_t hy){return abs64(x-y)<=hx+hy;}
int nd3d_touch(NdBox3 a,NdBox3 b){
    return overlap_axis(a.x,a.hx,b.x,b.hx) && overlap_axis(a.y,a.hy,b.y,b.hy) && overlap_axis(a.z,a.hz,b.z,b.hz);
}
int32_t nd3d_limit(NdBox3 a,int32_t target,int axis,NdBox3 b){
    int64_t current=axis==0?a.x:(axis==1?a.y:a.z);
    int64_t extent=axis==0?a.hx:(axis==1?a.hy:a.hz);
    int64_t wall=axis==0?b.x:(axis==1?b.y:b.z);
    int64_t wextent=axis==0?b.hx:(axis==1?b.hy:b.hz);
    if(axis!=0 && !overlap_axis(a.x,a.hx,b.x,b.hx))return target;
    if(axis!=1 && !overlap_axis(a.y,a.hy,b.y,b.hy))return target;
    if(axis!=2 && !overlap_axis(a.z,a.hz,b.z,b.hz))return target;
    if(target>current && current+extent<=wall-wextent){
        if((int64_t)target+extent>wall-wextent)return (int32_t)(wall-wextent-extent);
    } else if(target<current && current-extent>=wall+wextent){
        if((int64_t)target-extent<wall+wextent)return (int32_t)(wall+wextent+extent);
    }
    return target;
}
int nd3d_overlap(NdBox3 a,int sphere_a,NdBox3 b,int sphere_b){
    if(!sphere_a && !sphere_b)return nd3d_touch(a,b);
    /* Half extent of sphere is its radius; fixed values stay in int64 range. */
    if(sphere_a && sphere_b){
        int64_t dx=(int64_t)a.x-b.x,dy=(int64_t)a.y-b.y,dz=(int64_t)a.z-b.z;
        int64_t r=(int64_t)a.hx+b.hx;
        return dx*dx+dy*dy+dz*dz<r*r;
    }
    NdBox3 s=sphere_a?a:b, box=sphere_a?b:a;
    int64_t dx=(int64_t)s.x-clamp64(s.x,(int64_t)box.x-box.hx,(int64_t)box.x+box.hx);
    int64_t dy=(int64_t)s.y-clamp64(s.y,(int64_t)box.y-box.hy,(int64_t)box.y+box.hy);
    int64_t dz=(int64_t)s.z-clamp64(s.z,(int64_t)box.z-box.hz,(int64_t)box.z+box.hz);
    int64_t r=s.hx;
    return dx*dx+dy*dy+dz*dz<r*r;
}
