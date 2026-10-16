#ifndef NOVADS_RUNTIME_H
#define NOVADS_RUNTIME_H
#include <nds.h>
#include <stddef.h>
#include <stdint.h>

/* Binary scene API. This layout is the same for every exported project. */
typedef struct {
    int width, height;
    const u16 *tiles;          /* Nintendo DS 4bpp tiled sprite graphics */
    int tile_words;            /* count of 16-bit graphics words */
    const u16 *palette;        /* 16 RGB555 colors; index zero transparent */
} NdImage;

typedef struct {
    int id, type, screen;      /* type: 1 Cube3D; 2 Sprite2D; screen: 0 top, 1 bottom */
    int x,y,z,scale,spin;      /* cubes: 20.12 XYZ, half-side; spin DS rotation units */
    int speed,controllable;    /* sprites: x/y pixels; speed pixels/frame */
    int image;                 /* index in NdScene.images, -1 for cubes */
    int r,g,b;                 /* cube RGB5 */
    int script;                /* index in NdScene.programs, -1 none */
    int frame_count, fps256, loop, flip_x, flip_y;
    int sprite_angle, scale_x256, scale_y256, initial_frame;
    /* v0.7: 2D physics. Collider width/height 0 = sprite dimensions. */
    int collider, solid, trigger, physics, collider_w, collider_h;
    int velocity_x16, velocity_y16, gravity16, friction16;
    int collision_layer, collision_mask;
    int scene_index;       /* named scene ID, shared art/VRAM per project */
    int mesh_index;        /* -1 for primitives/sprites; 0..mesh_count-1 for Mesh3D */
    int rotation_x,rotation_y,rotation_z; /* DS 0..65535 turn angles */
    /* v0.9.2: independent 3D collider, all world dimensions stored in 16.16. */
    int collision3d, solid3d, trigger3d, physics3d, sphere3d;
    int half_x3d, half_y3d, half_z3d; /* half extents; radius for spheres */
    int velocity_x3d,velocity_y3d,velocity_z3d,gravity3d,friction3d;
    int collision_layer3d,collision_mask3d;
    int animation3d_index; /* -1 for no animation clip */
    int cull3d, lod_mesh_index, lod_distance16; /* v0.9.4 */
} NdObjectDef;

/* Full Lua source, embedded in ROM and loaded by the ARM9 VM. */
typedef struct {
    const unsigned char *source;
    unsigned int length;
    const char *name;
} NdScript;

typedef struct {
    const u16 *tiles;          /* 4bpp tiles with transparent tile 0 */
    int tile_words;
    const u16 *map;            /* 32x32 tile indices, 4bpp bank 1 */
    int map_words;
    const u16 *palette;        /* 16 entries per layer */
    int affine, scroll_x, scroll_y, angle, scale256;
    int map_width, map_height, parallax256;
    const char *name;
} NdBackground;

typedef struct {
    const unsigned char *bits; /* row-major bitset: 1 = solid tile */
    int width, height;          /* tiles, each tile 8x8 */
} NdTileCollision;

typedef struct {
    const char *name;
    const signed char *pcm8;
    unsigned int frames, rate;
} NdSound;

typedef struct { int16_t x,y,z; } NdMeshVertex;
typedef struct {
    u16 a,b,c,color;
    int16_t texture_index; /* -1 = untextured */
    int16_t u0,v0,u1,v1,u2,v2; /* DS 12.4 fixed-point TEX_COORD */
} NdMeshFace;
typedef struct {
    const u16 *pixels; /* direct RGBA5551 */
    int width,height;
} NdTexture;
typedef struct {
    const NdMeshVertex *vertices;
    const NdMeshFace *faces;
    int vertex_count, face_count;
    int radius12; /* conservative model-space bound in 4.12 */
} NdMesh;

typedef struct {
    int frame,dx,dy,dz,yaw,scale256; /* offsets and scale, frames in source FPS */
} NdAnimKey3D;
typedef struct {
    const char *name;
    const NdAnimKey3D *keys;
    int key_count;
    const u16 *mesh_frames; /* indices into NdScene.meshes, empty for transform-only */
    int mesh_frame_count;
    int duration, fps256, loop, autoplay;
} NdAnim3D;

typedef struct {
    int mode_3d2d;
    u16 top_color, bottom_color;
    int object_count;
    const NdObjectDef *objects;
    int image_count;
    const NdImage *images;
    int script_count;
    const NdScript *scripts;
    const NdBackground *backgrounds; /* top0, top1, bottom0, bottom1 */
    int follow_top, follow_bottom;
    const NdTileCollision *tile_collisions; /* four hardware BG slots */
    int scene_count, starting_scene;
    const char *const *scene_names;
    int sound_count;
    const NdSound *sounds;
    int mesh_count;
    const NdMesh *meshes;
    int texture_count;
    const NdTexture *textures;
    int camera_x,camera_y,camera_z; /* world coords 20.12 */
    int camera_yaw,camera_pitch; /* degrees as 65536-turn angles */
    int camera_fov; /* degrees */
    int animation3d_count;
    const NdAnim3D *animations3d;
    int frustum_culling, fog_enabled;
    u16 fog_color;
    int fog_density, brightness256, profiler;
    int dual3d, camera_bottom_x, camera_bottom_y, camera_bottom_z;
    int camera_bottom_yaw, camera_bottom_pitch, camera_bottom_fov;
} NdScene;

extern const NdScene nd_scene;
#endif
