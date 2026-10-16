#include "nd_physics.h"
#define F ((int64_t)65536)
static int64_t left(NdPhysRect a){return a.x;}
static int64_t right(NdPhysRect a){return (int64_t)a.x+(int64_t)a.w*F;}
static int64_t top(NdPhysRect a){return a.y;}
static int64_t bottom(NdPhysRect a){return (int64_t)a.y+(int64_t)a.h*F;}
static int crosses(int64_t a0,int64_t a1,int64_t b0,int64_t b1){return a0<b1&&a1>b0;}
int nd_physics_touch(NdPhysRect a,NdPhysRect b){
    int horizontal=crosses(left(a),right(a),left(b),right(b));
    int vertical=crosses(top(a),bottom(a),top(b),bottom(b));
    return (horizontal && top(a)<=bottom(b) && bottom(a)>=top(b)) ||
           (vertical && left(a)<=right(b) && right(a)>=left(b));
}
int32_t nd_physics_limit(NdPhysRect body,int32_t target,int axis,NdPhysRect wall){
    int64_t start=axis?body.y:body.x;
    int64_t length=(int64_t)(axis?body.h:body.w)*F;
    int64_t wall_start=axis?wall.y:wall.x;
    int64_t wall_end=wall_start+(int64_t)(axis?wall.h:wall.w)*F;
    int64_t body_other=axis?left(body):top(body);
    int64_t body_other_end=axis?right(body):bottom(body);
    int64_t wall_other=axis?left(wall):top(wall);
    int64_t wall_other_end=axis?right(wall):bottom(wall);
    if(!crosses(body_other,body_other_end,wall_other,wall_other_end))return target;
    if(target>start && start+length<=wall_start && (int64_t)target+length>wall_start){
        return (int32_t)(wall_start-length);
    }
    if(target<start && start>=wall_end && (int64_t)target<wall_end){
        return (int32_t)wall_end;
    }
    return target;
}
