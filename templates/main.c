/* NovaDS Studio v1.0 - Nintendo DS/DS Lite runtime.
 * Game content is in scene.c (generated from project JSON / imported PNGs).
 * The engine is the SAME C source for every exported project.
 * Uses DS 3D hardware + 2D OAM sprites; no DSi-specific assumptions.
 */
#include <nds.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdint.h>
#include "novads_runtime.h"
#include "scene.h"
#include "nd_physics.h"
#include "nd_physics3d.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

#define ND_MAX_OBJECTS 192
#define ND_MAX_IMAGES 256
#define ND_MAX_3D_TEXTURES 32
#define ND_MAX_SPRITES_PER_SCREEN 64
#define ND_PALETTE_BANKS 16
#define ND_SPRITE_DIAGNOSTICS 0

typedef struct {
    NdObjectDef def;
    int angle;             /* DS rotation units */
    int32_t x,y,z;        /* position in script-friendly 16.16 fixed point */
    bool visible;
    int oam_id;            /* assigned separately for top / bottom OAM */
    u16 *gfx;              /* shared gfx for sprite instances referencing same image */
    int palette_bank;
    int frame, anim_clock, fps256;
    int anim_playing, anim_loop, flip_x, flip_y;
    int scale_x256, scale_y256;
    int lua_env_ref;    /* per-object script environment in shared Lua VM */
    int32_t old_x,old_y;
    int32_t vx,vy,gravity,friction; /* 16.16 px/sec or px/sec^2 */
    int collider,solid,trigger,physics,grounded,collider_w,collider_h;
    int collision_layer,collision_mask;
    int32_t vz;
    int32_t half_x3d,half_y3d,half_z3d;
    int collider3d,solid3d,trigger3d,physics3d,sphere3d,grounded3d;
    int layer3d,mask3d;
    int anim3d_playing,anim3d_time256,anim3d_speed256,anim3d_mesh;
    int anim3d_last_x,anim3d_last_y,anim3d_last_z,anim3d_last_yaw;
    int anim3d_scale256;
} NdObject;
static NdObject objects[ND_MAX_OBJECTS];
static u16 *image_gfx[2][ND_MAX_IMAGES];
static signed char image_pal_bank[2][ND_MAX_IMAGES];
static int palette_count[2];
/* BG0 text, BG2/BG3 scenery; slots [top0,top1,bottom0,bottom1]. */
static PrintConsole ui_top,ui_bottom;
static PrintConsole *ui_consoles[2]={NULL,NULL};
typedef struct {
    int id,affine,x,y,angle,scale256,parallax256;
} NdBgRuntime;
static NdBgRuntime bg_layers[4]={{-1,0,0,0,0,256,256},{-1,0,0,0,0,256,256},
                                  {-1,0,0,0,0,256,256},{-1,0,0,0,0,256,256}};
static int camera_x[2]={0,0}, camera_y[2]={0};
static int follow_id[2]={0,0};
/* Previous frame contacts for Enter/Stay/Exit events (static 36 KiB). */
static unsigned char previous_contacts[ND_MAX_OBJECTS][ND_MAX_OBJECTS];
static int current_scene=0, requested_scene=-1;
static int touch_x=-1,touch_y=-1;
static int camera3_x,camera3_y,camera3_z,camera3_yaw,camera3_pitch;
static int camera_bottom_x,camera_bottom_y,camera_bottom_z,camera_bottom_yaw,camera_bottom_pitch;
static int dual3d_phase=0;
/* Dual 3D framebuffer mode: capture two alternating views in VRAM C/D.
 * VRAM A remains dedicated to textures. D can be displayed on SUB via
 * sixteen-color? No: 12 independent 64x64 direct-color bitmap OAM sprites.
 * The 2D UI, console, and normal sprite layer are unavailable in this mode.
 */
static int mesh_texture_ids[ND_MAX_3D_TEXTURES]; /* 0 means unavailable */
/* Every named scene shares one set of BGs/assets and a fixed object pool. */
static bool active_object(const NdObject *o) { return o->def.scene_index==current_scene; }


static const signed char FACES[6][4][3] = {
    {{-1,-1, 1},{ 1,-1, 1},{ 1, 1, 1},{-1, 1, 1}},
    {{ 1,-1,-1},{-1,-1,-1},{-1, 1,-1},{ 1, 1,-1}},
    {{-1,-1,-1},{-1,-1, 1},{-1, 1, 1},{-1, 1,-1}},
    {{ 1,-1, 1},{ 1,-1,-1},{ 1, 1,-1},{ 1, 1, 1}},
    {{-1, 1, 1},{ 1, 1, 1},{ 1, 1,-1},{-1, 1,-1}},
    {{-1,-1,-1},{ 1,-1,-1},{ 1,-1, 1},{-1,-1, 1}}
};

static void draw_cube(NdObject *o) {
    static const int shade[6] = {31,16,21,25,31,11};
    const NdObjectDef *c=&o->def;
    glPushMatrix();
    glTranslatef32(o->x >> 4,o->y >> 4,o->z >> 4);
    glRotateYi(o->angle);
    glRotateXi(o->angle/2);
    int render_scale=(int)(((int64_t)c->scale*o->anim3d_scale256)/256);
    glScalef32(render_scale,render_scale,render_scale);
    glBindTexture(0,0); /* Avoid sampling a previously bound mesh texture. */
    glBegin(GL_QUADS);
    for (int face=0;face<6;face++) {
        int r=(c->r*shade[face]*nd_scene.brightness256)/(31*256);
        int g=(c->g*shade[face]*nd_scene.brightness256)/(31*256);
        int b=(c->b*shade[face]*nd_scene.brightness256)/(31*256);
        if(r>31)r=31;if(g>31)g=31;if(b>31)b=31;
        glColor(RGB15(r,g,b));
        for (int v=0;v<4;v++) {
            glVertex3v16(inttov16(FACES[face][v][0]),
                         inttov16(FACES[face][v][1]),
                         inttov16(FACES[face][v][2]));
        }
    }
    glEnd();
    glPopMatrix(1);
}

/* Textured and flat faces share one V16 mesh path. All texture coordinates,
   vertex positions and color shading were baked on the PC. No UV math on ARM9. */
static void draw_mesh(NdObject *o,int override_mesh) {
    const NdObjectDef *d=&o->def;
    if(d->mesh_index<0 || d->mesh_index>=nd_scene.mesh_count)return;
    int mesh_index=override_mesh>=0 ? override_mesh : (o->anim3d_mesh>=0 ? o->anim3d_mesh : d->mesh_index);
    if(mesh_index<0 || mesh_index>=nd_scene.mesh_count)return;
    const NdMesh *mesh=&nd_scene.meshes[mesh_index];
    if(!mesh->vertices || !mesh->faces || mesh->face_count<=0)return;
    glPushMatrix();
    glTranslatef32(o->x>>4,o->y>>4,o->z>>4);
    glRotateYi(o->angle);
    glRotateXi(d->rotation_x);
    glRotateZi(d->rotation_z);
    int render_scale=(int)(((int64_t)d->scale*o->anim3d_scale256)/256);
    glScalef32(render_scale,render_scale,render_scale);
    int active_texture=-2;
    for(int i=0;i<mesh->face_count;) {
        const NdMeshFace *first=&mesh->faces[i];
        int texture=first->texture_index;
        if(texture<0 || texture>=nd_scene.texture_count ||
                texture>=ND_MAX_3D_TEXTURES || !mesh_texture_ids[texture])texture=-1;
        if(texture!=active_texture) {
            glBindTexture(0,texture>=0 ? mesh_texture_ids[texture] : 0);
            active_texture=texture;
        }
        /* One glBegin for each adjacent run of faces with the same texture. */
        glBegin(GL_TRIANGLES);
        do {
            const NdMeshFace *f=&mesh->faces[i];
            const NdMeshVertex *a=&mesh->vertices[f->a];
            const NdMeshVertex *b=&mesh->vertices[f->b];
            const NdMeshVertex *c=&mesh->vertices[f->c];
            glColor(f->color);
            if(texture>=0)glTexCoord2t16(f->u0,f->v0);
            glVertex3v16(a->x,a->y,a->z);
            if(texture>=0)glTexCoord2t16(f->u1,f->v1);
            glVertex3v16(b->x,b->y,b->z);
            if(texture>=0)glTexCoord2t16(f->u2,f->v2);
            glVertex3v16(c->x,c->y,c->z);
            i++;
            if(i>=mesh->face_count)break;
            int next=mesh->faces[i].texture_index;
            if(next<0 || next>=nd_scene.texture_count ||
                    next>=ND_MAX_3D_TEXTURES || !mesh_texture_ids[next])next=-1;
            if(next!=texture)break;
        }while(1);
        glEnd();
    }
    glBindTexture(0,0);
    glPopMatrix(1);
}

/* libnds requires GL_TEXTURE_SIZE_ENUM values here, NOT pixel counts.
   In devkitPro/libnds a 64x64 texture is TEXTURE_SIZE_64 (3), not 64.
   Passing pixels makes the VRAM allocation and GFX_TEX_FORMAT invalid. */
static int texture_size_enum(int pixels) {
    switch (pixels) {
        case 8: return TEXTURE_SIZE_8;
        case 16: return TEXTURE_SIZE_16;
        case 32: return TEXTURE_SIZE_32;
        case 64: return TEXTURE_SIZE_64;
        case 128: return TEXTURE_SIZE_128;
        default: return -1;  /* already rejected by the PC exporter */
    }
}

static void load_mesh_textures(void) {
    if(nd_scene.texture_count<=0)return;
    if(nd_scene.texture_count>ND_MAX_3D_TEXTURES)return;
    /* A = 128 KiB 3D textures; B = top OBJ; C/D = bottom BG/OBJ. */
    vramSetBankA(VRAM_A_TEXTURE);
    glEnable(GL_TEXTURE_2D);
    int failed=0;
    for(int i=0;i<nd_scene.texture_count;i++) {
        const NdTexture *t=&nd_scene.textures[i];
        if(!t->pixels){failed++;continue;}
        int tw=texture_size_enum(t->width);
        int th=texture_size_enum(t->height);
        if(tw<0 || th<0){failed++;continue;}
        glGenTextures(1,&mesh_texture_ids[i]);
        if(!mesh_texture_ids[i]){failed++;continue;}
        glBindTexture(0,mesh_texture_ids[i]);
        if(!glTexImage2D(0,0,GL_RGBA,tw,th,0,
                            TEXGEN_TEXCOORD,t->pixels)) {
            mesh_texture_ids[i]=0;
            failed++;
        }
    }
    glBindTexture(0,0);
    /* On a real DS, don't silently hide failed GPU uploads. */
    if(failed) {
        consoleSelect(&ui_bottom);
        iprintf("\x1b[1;0H3D TEX LOAD FAIL: %d/%d",failed,nd_scene.texture_count);
    }
}

static SpriteSize image_size(const NdImage *im) {
    if (im->width==8 && im->height==8) return SpriteSize_8x8;
    if (im->width==16 && im->height==16) return SpriteSize_16x16;
    if (im->width==32 && im->height==32) return SpriteSize_32x32;
    if (im->width==64 && im->height==64) return SpriteSize_64x64;
    if (im->width==16 && im->height==8) return SpriteSize_16x8;
    if (im->width==32 && im->height==8) return SpriteSize_32x8;
    if (im->width==32 && im->height==16) return SpriteSize_32x16;
    if (im->width==64 && im->height==32) return SpriteSize_64x32;
    if (im->width==8 && im->height==16) return SpriteSize_8x16;
    if (im->width==8 && im->height==32) return SpriteSize_8x32;
    if (im->width==16 && im->height==32) return SpriteSize_16x32;
    if (im->width==32 && im->height==64) return SpriteSize_32x64;
    /* other sizes rejected by exporter, so should never hit this path */
    return SpriteSize_16x16;
}

static bool valid_dims(const NdImage *im) {
    /* DS hardware supports only these sprite aspect ratios. */
    int w=im->width, h=im->height;
    return (w==8 && (h==8 || h==16 || h==32)) ||
           (w==16 && (h==8 || h==16 || h==32)) ||
           (w==32 && (h==8 || h==16 || h==32 || h==64)) ||
           (w==64 && (h==32 || h==64));
}

/* Safe per-engine BG VRAM arrangement:
   BG0 text: charbase 0, mapbase 30.
   BG2: charbase 1 (0x4000), mapbase 20..23 (512x512 max).
   BG3: charbase 2 (0x8000), mapbase 24..27.
   BG2/BG3 get palette bank 1/2; console palette bank 0.
   Affine mode only permits one layer per screen in the exporter.
*/
static void init_background(int screen,int slot) {
    int index=screen*2+slot;
    const NdBackground *src=&nd_scene.backgrounds[index];
    NdBgRuntime *b=&bg_layers[index];
    if (!src->tiles || !src->map) return;
    int bg=2+slot, map_base=20+slot*4, char_base=1+slot;
    bool large=src->map_width==64 || src->map_height==64;
    int size=src->affine ? (large ? BgSize_ER_512x512 : BgSize_ER_256x256)
                          : (large ? BgSize_T_512x512 : BgSize_T_256x256);
    /* Non-square maps use the same 512x512 hardware allocation; export pads them. */
    int id=screen ? bgInitSub(bg,src->affine ? BgType_ExRotation : BgType_Text4bpp,
                              size,map_base,char_base)
                  : bgInit(bg,src->affine ? BgType_ExRotation : BgType_Text4bpp,
                           size,map_base,char_base);
    bgSetPriority(id,2+slot); /* BG2 nearer than BG3; UI BG0 always on top */
    if(src->affine)bgWrapOn(id);
    volatile u16 *tiles=(volatile u16*)bgGetGfxPtr(id);
    volatile u16 *map=(volatile u16*)bgGetMapPtr(id);
    for(int i=0;i<src->tile_words;i++)tiles[i]=src->tiles[i];
    for(int i=0;i<src->map_words;i++) {
        u16 entry=src->map[i];
        if(!src->affine)entry=(entry&0x0FFF)|((slot+1)<<12);
        map[i]=entry;
    }
    volatile u16 *palette=screen ? BG_PALETTE_SUB : BG_PALETTE;
    for(int i=0;i<16;i++)palette[16*(slot+1)+i]=src->palette[i];
    b->id=id;b->affine=src->affine;b->x=src->scroll_x;b->y=src->scroll_y;
    b->angle=src->angle;b->scale256=src->scale256;b->parallax256=src->parallax256;
}

static void update_backgrounds(void) {
    for(int i=0;i<4;i++) {
        NdBgRuntime *b=&bg_layers[i];
        if(b->id<0)continue;
        int screen=i/2;
        int x=b->x+(int)(((long long)camera_x[screen]*b->parallax256)/256);
        int y=b->y+(int)(((long long)camera_y[screen]*b->parallax256)/256);
        if(b->affine)bgSet(b->id,b->angle,b->scale256,b->scale256,
                           x*256,y*256,128*256,96*256);
        else bgSetScroll(b->id,x,y);
    }
    bgUpdate();
}

/* The 3D framebuffer is 256x192, stored as 16-bit scanlines in C or D.
 * C can be mapped to SUB BG3 directly. D cannot, so SUB OAM displays D
 * using twelve 64x64 BMP sprites with 2D 256-pixel pitch.
 * Hardware display engines swap physical screens on alternating frames.
 */
static void init_dual3d_video(void) {
    videoSetModeSub(MODE_5_2D);
    vramSetBankC(VRAM_C_LCD);
    vramSetBankD(VRAM_D_LCD);
    for(int i=0;i<256*192;i++){
        VRAM_C[i]=0x8000 | nd_scene.bottom_color;
        VRAM_D[i]=0x8000 | nd_scene.top_color;
    }
    /* BG3 reads a 256x256 16-bit linear framebuffer from bank C. */
    vramSetBankC(VRAM_C_SUB_BG);
    int framebuffer_bg=bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);
    /* Identity BG3 affine transform; use libnds rather than raw SUB regs. */
    bgSet(framebuffer_bg,0,256,256,0,0,0,0);
    bgUpdate();
    vramSetBankD(VRAM_D_SUB_SPRITE);
    oamInit(&oamSub,SpriteMapping_Bmp_2D_256,false);
    oamEnable(&oamSub);
    for(int row=0;row<3;row++)for(int col=0;col<4;col++){
        int id=row*4+col;
        /* Bitmap 2D addressing: the next image line begins 256 pixels later. */
        u16 *gfx=(u16*)(0x06600000 + ((row*64*256)+(col*64))*2);
        oamSet(&oamSub,id,col*64,row*64,0,15,SpriteSize_64x64,
               SpriteColorFormat_Bmp,gfx,-1,false,false,false,false,false);
    }
    oamUpdate(&oamSub);
    camera3_x=nd_scene.camera_x;camera3_y=nd_scene.camera_y;camera3_z=nd_scene.camera_z;
    camera3_yaw=nd_scene.camera_yaw;camera3_pitch=nd_scene.camera_pitch;
    camera_bottom_x=nd_scene.camera_bottom_x;
    camera_bottom_y=nd_scene.camera_bottom_y;
    camera_bottom_z=nd_scene.camera_bottom_z;
    camera_bottom_yaw=nd_scene.camera_bottom_yaw;
    camera_bottom_pitch=nd_scene.camera_bottom_pitch;
}

/* VBlank-safe bank switching. The LCD display reads the *previous* image
 * while the capture unit records the current 3D render into its bank.
 * phase 0: main LCD=top shows D, sub LCD=bottom shows C.
 * phase 1: main LCD=bottom shows C, sub LCD=top shows D.
 */
static void dual3d_begin_frame(int phase){
    REG_DISPCAPCNT=0; /* Stop capture before remapping C/D. */
    if(phase==0){
        vramSetBankD(VRAM_D_LCD);vramSetBankC(VRAM_C_SUB_BG);
        lcdMainOnTop();
        videoSetMode(MODE_FB3);
        REG_DISPCNT_SUB=(REG_DISPCNT_SUB & ~(DISPLAY_BG3_ACTIVE|DISPLAY_SPR_ACTIVE)) | DISPLAY_BG3_ACTIVE;
    }else{
        vramSetBankC(VRAM_C_LCD);vramSetBankD(VRAM_D_SUB_SPRITE);
        lcdMainOnBottom();
        videoSetMode(MODE_FB2);
        REG_DISPCNT_SUB=(REG_DISPCNT_SUB & ~(DISPLAY_BG3_ACTIVE|DISPLAY_SPR_ACTIVE)) | DISPLAY_SPR_ACTIVE;
    }
    glClearColor((phase==0 ? nd_scene.top_color : nd_scene.bottom_color)&31,
                 ((phase==0 ? nd_scene.top_color : nd_scene.bottom_color)>>5)&31,
                 ((phase==0 ? nd_scene.top_color : nd_scene.bottom_color)>>10)&31,31);
    REG_DISPCAPCNT=DCAP_ENABLE | DCAP_MODE_A | DCAP_SRC_A(1) |
                    DCAP_SIZE(DCAP_SIZE_256x192) | DCAP_A(16) |
                    DCAP_BANK(phase==0 ? DCAP_BANK_VRAM_D : DCAP_BANK_VRAM_C);
}

static void init_2d_video(void) {
    lcdMainOnTop();
    if(nd_scene.dual3d){init_dual3d_video();goto init_3d_only;}
    if (nd_scene.mode_3d2d) {
        videoSetMode(MODE_0_3D);
        vramSetBankB(VRAM_B_MAIN_SPRITE);
    } else {
        videoSetMode(nd_scene.backgrounds[0].affine ? MODE_5_2D : MODE_0_2D);
        vramSetBankA(VRAM_A_MAIN_SPRITE);
        vramSetBankB(VRAM_B_MAIN_BG_0x06000000);
        /* Top BG0 belongs to the MAIN graphics engine, not SUB. */
        consoleInit(&ui_top,0,BgType_Text4bpp,BgSize_T_256x256,
                    30,0,true,true);
        bgSetPriority(ui_top.bgId,0);
        ui_consoles[0]=&ui_top;
        BG_PALETTE[0]=nd_scene.top_color;
    }
    oamInit(&oamMain,SpriteMapping_1D_128,false);
    oamEnable(&oamMain);

    videoSetModeSub(nd_scene.backgrounds[2].affine ? MODE_5_2D : MODE_0_2D);
    vramSetBankC(VRAM_C_SUB_BG);
    vramSetBankD(VRAM_D_SUB_SPRITE);
    oamInit(&oamSub,SpriteMapping_1D_128,false);
    oamEnable(&oamSub);
    /* Allocate separate console structures; consoleInit(NULL) reuses one. */
    consoleInit(&ui_bottom,0,BgType_Text4bpp,BgSize_T_256x256,
                30,0,false,true);
    bgSetPriority(ui_bottom.bgId,0);
    ui_consoles[1]=&ui_bottom;
    consoleSelect(&ui_bottom);
    oamEnable(&oamSub);
    BG_PALETTE_SUB[0]=nd_scene.bottom_color;
    if(!nd_scene.backgrounds[2].tiles) {
        iprintf("\x1b[21;1HD-pad: move");
        iprintf("\x1b[22;1HTouch: teleport");
    }
    if(!nd_scene.mode_3d2d){init_background(0,0);init_background(0,1);}
    init_background(1,0);init_background(1,1);
    camera3_x=nd_scene.camera_x;camera3_y=nd_scene.camera_y;camera3_z=nd_scene.camera_z;
    camera3_yaw=nd_scene.camera_yaw;camera3_pitch=nd_scene.camera_pitch;
    follow_id[0]=nd_scene.follow_top;follow_id[1]=nd_scene.follow_bottom;
    update_backgrounds();

    init_3d_only:
    if (nd_scene.mode_3d2d) {
        glInit();
        glEnable(GL_ANTIALIAS);
        glClearColor(nd_scene.top_color&31,(nd_scene.top_color>>5)&31,
                     (nd_scene.top_color>>10)&31,31);
        glClearPolyID(63);
        glClearDepth(0x7FFF);
        glViewport(0,0,255,191);
        glPolyFmt(POLY_ALPHA(31)|POLY_CULL_NONE|(nd_scene.fog_enabled?POLY_FOG:0));
        if(nd_scene.fog_enabled){
            glEnable(GL_FOG);
            glFogColor(nd_scene.fog_color&31,(nd_scene.fog_color>>5)&31,(nd_scene.fog_color>>10)&31,31);
            glFogOffset(0);
            glFogShift(1);
            for(int i=0;i<32;i++)glFogDensity(i,(i*nd_scene.fog_density)/31);
        }
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity();
        gluPerspective(nd_scene.camera_fov,256.0f/192.0f,0.1f,50.0f);
        load_mesh_textures();
    }
}

/* One palette per animation, not per frame; shared frames uploaded once per screen. */
static void upload_animation(int screen,int first,int count) {
    if (first<0 || count<1 || first+count>nd_scene.image_count)return;
    if (image_gfx[screen][first])return;
    if (palette_count[screen]>=ND_PALETTE_BANKS)return;
    OamState *oam=screen ? &oamSub : &oamMain;
    /* Never publish the first frame until every frame was uploaded. */
    u16 *allocated[16]={0};
    if (count>16)return;
    for(int f=0;f<count;f++) {
        const NdImage *im=&nd_scene.images[first+f];
        if(!valid_dims(im))goto rollback_animation;
        allocated[f]=oamAllocateGfx(oam,image_size(im),SpriteColorFormat_16Color);
        if(!allocated[f])goto rollback_animation;
        volatile u16 *dst=(volatile u16*)allocated[f];
        for(int i=0;i<im->tile_words;i++)dst[i]=im->tiles[i];
    }
    {
        int bank=palette_count[screen]++;
        u16 *pal=screen ? SPRITE_PALETTE_SUB : SPRITE_PALETTE;
        for(int i=0;i<16;i++)pal[bank*16+i]=nd_scene.images[first].palette[i];
        for(int f=0;f<count;f++) {
            image_gfx[screen][first+f]=allocated[f];
            image_pal_bank[screen][first+f]=(signed char)bank;
        }
    }
    return;
rollback_animation:
    for(int f=0;f<count;f++)if(allocated[f])oamFreeGfx(oam,allocated[f]);
}

static void load_scene(void) {
    int top_oam=0,bottom_oam=0;
    if (nd_scene.object_count>ND_MAX_OBJECTS || nd_scene.image_count>ND_MAX_IMAGES)
        return;  /* Exporter validates; defensive runtime guard. */
    for (int i=0;i<2;i++) for (int j=0;j<ND_MAX_IMAGES;j++)
        image_pal_bank[i][j]=-1;
    for (int i=0;i<nd_scene.object_count;i++) {
        NdObject *o=&objects[i];
        o->def=nd_scene.objects[i];
        o->angle=(o->def.type==2 ? o->def.sprite_angle : o->def.rotation_y);
        o->oam_id=-1; o->gfx=NULL; o->palette_bank=0;
        o->frame=o->def.initial_frame; o->fps256=o->def.fps256;
        o->anim_clock=0; o->anim_loop=o->def.loop;
        o->anim_playing=(o->fps256>0 && o->def.frame_count>1);
        o->flip_x=o->def.flip_x; o->flip_y=o->def.flip_y;
        o->scale_x256=o->def.scale_x256 ? o->def.scale_x256 : 256;
        o->scale_y256=o->def.scale_y256 ? o->def.scale_y256 : 256;
        o->visible=true; o->lua_env_ref=LUA_NOREF;
        o->anim3d_time256=0;o->anim3d_speed256=256;
        o->anim3d_mesh=-1;o->anim3d_scale256=256;
        o->anim3d_last_x=o->anim3d_last_y=o->anim3d_last_z=o->anim3d_last_yaw=0;
        o->anim3d_playing=0;
        if(o->def.animation3d_index>=0 && o->def.animation3d_index<nd_scene.animation3d_count)
            o->anim3d_playing=nd_scene.animations3d[o->def.animation3d_index].autoplay;
        o->collider=o->def.collider;o->solid=o->def.solid;
        o->trigger=o->def.trigger;o->physics=o->def.physics;
        o->collider_w=o->def.collider_w;o->collider_h=o->def.collider_h;
        o->vx=o->def.velocity_x16;o->vy=o->def.velocity_y16;
        o->gravity=o->def.gravity16;o->friction=o->def.friction16;
        o->collision_layer=o->def.collision_layer;
        o->collision_mask=o->def.collision_mask;
        o->grounded=0;
        o->collider3d=o->def.collision3d;o->solid3d=o->def.solid3d;
        o->trigger3d=o->def.trigger3d;o->physics3d=o->def.physics3d;
        o->sphere3d=o->def.sphere3d;o->grounded3d=0;
        o->half_x3d=o->def.half_x3d;o->half_y3d=o->def.half_y3d;o->half_z3d=o->def.half_z3d;
        o->layer3d=o->def.collision_layer3d;o->mask3d=o->def.collision_mask3d;
        if(o->def.type==1 || o->def.type==3){
            o->vx=o->def.velocity_x3d;o->vy=o->def.velocity_y3d;o->vz=o->def.velocity_z3d;
            o->gravity=o->def.gravity3d;o->friction=o->def.friction3d;
        }else o->vz=0;
        if (o->def.type==1 || o->def.type==3) {
            o->x=o->def.x*16; o->y=o->def.y*16; o->z=o->def.z*16;
        } else {
            o->x=o->def.x*65536; o->y=o->def.y*65536; o->z=0;
        }
        if (o->def.type!=2) continue;
        int screen=o->def.screen, asset=o->def.image;
        if (asset<0 || asset>=nd_scene.image_count || screen<0 || screen>1) continue;
        int *idx=screen ? &bottom_oam : &top_oam;
        if (*idx>=ND_MAX_SPRITES_PER_SCREEN) continue;
        upload_animation(screen,asset,o->def.frame_count);
        o->gfx=image_gfx[screen][asset];
        if (o->gfx) {
            o->oam_id=(*idx)++;
            o->palette_bank=image_pal_bank[screen][asset];
        }
    }
#if ND_SPRITE_DIAGNOSTICS
    iprintf("\x1b[1;1HOBJ top=%d bottom=%d",top_oam,bottom_oam);
#endif
}

/* Scripted objects use Lua for input; built-in movement is only for un-scripted objects. */

/* -------------------------------- Lua VM ---------------------------------
 * One shared Lua 5.4 VM, one _ENV table per scene object. Top-level local
 * variables live in closures: each instance gets its own independent state.
 * No asset filesystem is required; scripts are embedded in scene.c.
 */
#define ND_LUA_BYTES (768u*1024u)
#define ND_LUA_INSTRUCTIONS 35000

typedef union { size_t length; double align_d; void *align_p; } LuaBlock;
static size_t lua_bytes=0;
static lua_State *nd_lua=NULL;
static int held_keys=0,pressed_keys=0;
static int lua_steps=0;
/* Lua registry reference needed by raycasts and scene lookups. */
static int object_table_ref=LUA_NOREF;

static void *budget_alloc(void *ud,void *ptr,size_t oldsize,size_t nsize) {
    (void)ud; (void)oldsize;
    LuaBlock *old = ptr ? ((LuaBlock *)ptr)-1 : NULL;
    size_t oldlen = old ? old->length : 0;
    if (nsize==0) {
        if (old) { lua_bytes-=oldlen; free(old); }
        return NULL;
    }
    if (nsize>ND_LUA_BYTES || lua_bytes-oldlen>ND_LUA_BYTES-nsize) return NULL;
    LuaBlock *newblock=(LuaBlock *)realloc(old,sizeof(LuaBlock)+nsize);
    if (!newblock) return NULL;
    newblock->length=nsize;
    lua_bytes=lua_bytes-oldlen+nsize;
    return newblock+1;
}

static void vm_hook(lua_State *L,lua_Debug *ar) {
    (void)ar;
    lua_steps+=500;
    if (lua_steps>=ND_LUA_INSTRUCTIONS)
        luaL_error(L,"script instruction budget exceeded");
}

static int guarded_call(lua_State *L,int nargs,int nresults) {
    lua_steps=0;
    int status=lua_pcall(L,nargs,nresults,0);
    if (status!=LUA_OK) {
        const char *err=lua_tostring(L,-1);
        iprintf("\x1b[2;1H%-31.31s",err ? err : "Lua error");
        lua_pop(L,1);
    }
    return status;
}

static NdObject *check_object(lua_State *L,int index) {
    int *id=(int*)luaL_checkudata(L,index,"NovaDS.Object");
    if (*id<0 || *id>=nd_scene.object_count) luaL_error(L,"invalid object");
    return &objects[*id];
}

static int field_equals(const char *field,const char *value) {
    return strcmp(field,value)==0;
}

static const NdAnim3D *object_anim3d(NdObject *o);

static int push_field(lua_State *L,NdObject *o,const char *key) {
    if (field_equals(key,"id")) {lua_pushinteger(L,o->def.id); return 1;}
    if (field_equals(key,"name")) {lua_pushstring(L,"Object"); return 1;}
    if (field_equals(key,"x")) {lua_pushnumber(L,o->x/65536.0);return 1;}
    if (field_equals(key,"y")) {lua_pushnumber(L,o->y/65536.0);return 1;}
    if (field_equals(key,"z")) {lua_pushnumber(L,o->z/65536.0);return 1;}
    if (field_equals(key,"angle")) {lua_pushnumber(L,o->angle*(360.0/65536.0));return 1;}
    if (field_equals(key,"visible")) {lua_pushboolean(L,o->visible);return 1;}
    if (field_equals(key,"speed")) {lua_pushinteger(L,o->def.speed);return 1;}
    if(o->def.type==1 || o->def.type==3){
        if(field_equals(key,"animationPlaying")){lua_pushboolean(L,o->anim3d_playing);return 1;}
        if(field_equals(key,"animationTime")){lua_pushnumber(L,o->anim3d_time256/256.0);return 1;}
        if(field_equals(key,"animationSpeed")){lua_pushnumber(L,o->anim3d_speed256/256.0);return 1;}
        if(field_equals(key,"animationName")){
            const NdAnim3D *clip=object_anim3d(o);
            if(clip)lua_pushstring(L,clip->name);else lua_pushnil(L);
            return 1;
        }
        if(field_equals(key,"vx")){lua_pushnumber(L,o->vx/65536.0);return 1;}
        if(field_equals(key,"vy")){lua_pushnumber(L,o->vy/65536.0);return 1;}
        if(field_equals(key,"vz")){lua_pushnumber(L,o->vz/65536.0);return 1;}
        if(field_equals(key,"gravity")){lua_pushnumber(L,o->gravity/65536.0);return 1;}
        if(field_equals(key,"friction")){lua_pushnumber(L,o->friction/65536.0);return 1;}
        if(field_equals(key,"grounded")){lua_pushboolean(L,o->grounded3d);return 1;}
        if(field_equals(key,"physics")){lua_pushboolean(L,o->physics3d);return 1;}
        if(field_equals(key,"collider")){lua_pushboolean(L,o->collider3d);return 1;}
        if(field_equals(key,"solid")){lua_pushboolean(L,o->solid3d);return 1;}
        if(field_equals(key,"trigger")){lua_pushboolean(L,o->trigger3d);return 1;}
        if(field_equals(key,"sphere")){lua_pushboolean(L,o->sphere3d);return 1;}
        if(field_equals(key,"collisionLayer")){lua_pushinteger(L,o->layer3d);return 1;}
        if(field_equals(key,"collisionMask")){lua_pushinteger(L,o->mask3d);return 1;}
    }
    if (o->def.type==2) {
        if (field_equals(key,"flipX")) {lua_pushboolean(L,o->flip_x);return 1;}
        if (field_equals(key,"flipY")) {lua_pushboolean(L,o->flip_y);return 1;}
        if (field_equals(key,"scaleX")) {lua_pushnumber(L,o->scale_x256/256.0);return 1;}
        if (field_equals(key,"scaleY")) {lua_pushnumber(L,o->scale_y256/256.0);return 1;}
        if (field_equals(key,"frame")) {lua_pushinteger(L,o->frame);return 1;}
        if (field_equals(key,"frameCount")) {lua_pushinteger(L,o->def.frame_count);return 1;}
        if (field_equals(key,"fps")) {lua_pushnumber(L,o->fps256/256.0);return 1;}
        if (field_equals(key,"playing")) {lua_pushboolean(L,o->anim_playing);return 1;}
        if (field_equals(key,"loop")) {lua_pushboolean(L,o->anim_loop);return 1;}
        if (field_equals(key,"vx")) {lua_pushnumber(L,o->vx/65536.0);return 1;}
        if (field_equals(key,"vy")) {lua_pushnumber(L,o->vy/65536.0);return 1;}
        if (field_equals(key,"gravity")) {lua_pushnumber(L,o->gravity/65536.0);return 1;}
        if (field_equals(key,"friction")) {lua_pushnumber(L,o->friction/65536.0);return 1;}
        if (field_equals(key,"grounded")) {lua_pushboolean(L,o->grounded);return 1;}
        if (field_equals(key,"physics")) {lua_pushboolean(L,o->physics);return 1;}
        if (field_equals(key,"collider")) {lua_pushboolean(L,o->collider);return 1;}
        if (field_equals(key,"solid")) {lua_pushboolean(L,o->solid);return 1;}
        if (field_equals(key,"trigger")) {lua_pushboolean(L,o->trigger);return 1;}
        if (field_equals(key,"collisionLayer")) {lua_pushinteger(L,o->collision_layer);return 1;}
        if (field_equals(key,"collisionMask")) {lua_pushinteger(L,o->collision_mask);return 1;}
    }
    return 0;
}

static int property_set(lua_State *L,NdObject *o,const char *key,int val_index) {
    if (field_equals(key,"visible")) {o->visible=lua_toboolean(L,val_index)!=0;return 1;}
    if (field_equals(key,"id") || field_equals(key,"name"))
        return luaL_error(L,"read-only property: %s",key);
    if (field_equals(key,"x") || field_equals(key,"y") || field_equals(key,"z")) {
        double v=luaL_checknumber(L,val_index)*65536.0;
        if (v>2147483647.0 || v< -2147483647.0) return luaL_error(L,"position out of range");
        if (key[0]=='x')o->x=(int32_t)v;
        else if (key[0]=='y')o->y=(int32_t)v;
        else o->z=(int32_t)v;
        return 1;
    }
    if (field_equals(key,"angle")) {
        double d=luaL_checknumber(L,val_index);
        if (d>10000000.0 || d< -10000000.0) return luaL_error(L,"angle out of range");
        o->angle=((int)(d*(65536.0/360.0)))&65535;
        return 1;
    }
    if(o->def.type==1 || o->def.type==3){
        if(field_equals(key,"animationSpeed")){
            double n=luaL_checknumber(L,val_index);
            if(!isfinite(n) || n<0.1 || n>4.0)return luaL_error(L,"animationSpeed must be 0.1..4");
            o->anim3d_speed256=(int)(n*256+0.5);return 1;
        }
        if(field_equals(key,"animationPlaying")){
            o->anim3d_playing=lua_toboolean(L,val_index)!=0;return 1;
        }
        if(field_equals(key,"animationTime") || field_equals(key,"animationName"))
            return luaL_error(L,"read-only animation property");
        if(field_equals(key,"grounded"))return luaL_error(L,"grounded is read-only");
        if(field_equals(key,"physics")){o->physics3d=lua_toboolean(L,val_index);return 1;}
        if(field_equals(key,"collider")){o->collider3d=lua_toboolean(L,val_index);return 1;}
        if(field_equals(key,"solid")){o->solid3d=lua_toboolean(L,val_index);if(o->solid3d)o->trigger3d=0;return 1;}
        if(field_equals(key,"trigger")){o->trigger3d=lua_toboolean(L,val_index);if(o->trigger3d)o->solid3d=0;return 1;}
        if(field_equals(key,"collisionLayer") || field_equals(key,"collisionMask")){
            lua_Integer n=luaL_checkinteger(L,val_index);
            if(n<0 || n>255 || (field_equals(key,"collisionLayer") && n==0))
                return luaL_error(L,"collision bits outside allowed range");
            if(field_equals(key,"collisionLayer"))o->layer3d=(int)n;
            else o->mask3d=(int)n;
            return 1;
        }
        if(field_equals(key,"vx") || field_equals(key,"vy") || field_equals(key,"vz") ||
           field_equals(key,"gravity") || field_equals(key,"friction")){
            double n=luaL_checknumber(L,val_index);
            if(!isfinite(n) || n< -200 || n>200 || (field_equals(key,"friction") && n<0))
                return luaL_error(L,"3D physics value must be -200..200");
            int32_t fixed=(int32_t)(n*65536.0);
            if(field_equals(key,"vx"))o->vx=fixed;
            else if(field_equals(key,"vy"))o->vy=fixed;
            else if(field_equals(key,"vz"))o->vz=fixed;
            else if(field_equals(key,"gravity"))o->gravity=fixed;
            else o->friction=fixed;
            return 1;
        }
    }
    if (o->def.type==2) {
        if (field_equals(key,"flipX")) {o->flip_x=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"flipY")) {o->flip_y=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"playing")) {o->anim_playing=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"loop")) {o->anim_loop=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"grounded"))return luaL_error(L,"grounded is read-only");
        if (field_equals(key,"physics")) {o->physics=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"collider")) {o->collider=lua_toboolean(L,val_index);return 1;}
        if (field_equals(key,"solid")) {o->solid=lua_toboolean(L,val_index); if(o->solid)o->trigger=0;return 1;}
        if (field_equals(key,"trigger")) {o->trigger=lua_toboolean(L,val_index);if(o->trigger)o->solid=0;return 1;}
        if (field_equals(key,"collisionLayer") || field_equals(key,"collisionMask")) {
            lua_Integer value=luaL_checkinteger(L,val_index);
            if(value<0 || value>255 || (key[9]=='L' && value==0))
                return luaL_error(L,"collision layer/mask must be 0..255 (layer nonzero)");
            if (field_equals(key,"collisionLayer"))o->collision_layer=(int)value;
            else o->collision_mask=(int)value;
            return 1;
        }
        if (field_equals(key,"vx") || field_equals(key,"vy") ||
            field_equals(key,"gravity") || field_equals(key,"friction")) {
            double v=luaL_checknumber(L,val_index);
            double maximum=field_equals(key,"gravity") || field_equals(key,"friction") ? 4000.0 : 1024.0;
            double minimum=field_equals(key,"friction") ? 0.0 : -maximum;
            if(!(v>=minimum && v<=maximum))return luaL_error(L,"physics value outside allowed range");
            int32_t fixed=(int32_t)(v*65536.0);
            if (field_equals(key,"vx"))o->vx=fixed;
            else if (field_equals(key,"vy"))o->vy=fixed;
            else if (field_equals(key,"gravity"))o->gravity=fixed;
            else o->friction=fixed;
            return 1;
        }
        if (field_equals(key,"frameCount"))return luaL_error(L,"frameCount is read-only");
        if (field_equals(key,"frame")) {
            lua_Integer n=luaL_checkinteger(L,val_index);
            if(n<0 || n>=o->def.frame_count)return luaL_error(L,"frame outside sprite sheet");
            o->frame=(int)n;o->anim_clock=0;return 1;
        }
        if(field_equals(key,"scaleX") || field_equals(key,"scaleY")) {
            double n=luaL_checknumber(L,val_index);
            if(!(n>=0.25 && n<=4.0))return luaL_error(L,"sprite scale must be 0.25..4.0");
            if(field_equals(key,"scaleX"))o->scale_x256=(int)(n*256+0.5);
            else o->scale_y256=(int)(n*256+0.5);
            return 1;
        }
        if(field_equals(key,"fps")) {
            double n=luaL_checknumber(L,val_index);
            if(!(n>=0 && n<=60))return luaL_error(L,"animation fps must be 0..60");
            o->fps256=(int)(n*256+0.5);return 1;
        }
    }
    if (field_equals(key,"speed")) {
        int speed=(int)luaL_checkinteger(L,val_index);
        if (speed<0 || speed>32) return luaL_error(L,"speed must be 0..32");
        o->def.speed=speed;
        return 1;
    }
    return 0;
}

static int lua_object_move(lua_State *L) {
    NdObject *o=check_object(L,1);
    double dx=luaL_checknumber(L,2)*65536.0;
    double dy=luaL_checknumber(L,3)*65536.0;
    if (dx>10000000 || dx< -10000000 || dy>10000000 || dy< -10000000)
        return luaL_error(L,"movement out of range");
    double x=(double)o->x+dx,y=(double)o->y+dy;
    if (x>2147483647.0 || x< -2147483647.0 || y>2147483647.0 || y< -2147483647.0)
        return luaL_error(L,"position out of range");
    o->x=(int32_t)x;o->y=(int32_t)y;
    if(o->def.type!=2 && !lua_isnoneornil(L,4)){
        double dz=luaL_checknumber(L,4)*65536.0;
        double z=(double)o->z+dz;
        if(!isfinite(z) || z>2147483647.0 || z< -2147483647.0)
            return luaL_error(L,"3D movement out of range");
        o->z=(int32_t)z;
    }
    return 0;
}

/* A lightweight baked 3D clip: one clip per 3D object in v0.9.4. */
static const NdAnim3D *object_anim3d(NdObject *o){
    int n=o->def.animation3d_index;
    return (n>=0 && n<nd_scene.animation3d_count) ? &nd_scene.animations3d[n] : NULL;
}
static void reset_anim3d(NdObject *o){
    o->x-=o->anim3d_last_x;o->y-=o->anim3d_last_y;o->z-=o->anim3d_last_z;
    o->angle=(o->angle-o->anim3d_last_yaw)&65535;
    o->anim3d_last_x=o->anim3d_last_y=o->anim3d_last_z=o->anim3d_last_yaw=0;
    o->anim3d_scale256=256;o->anim3d_mesh=-1;o->anim3d_time256=0;
}
static int lua_object_play_animation(lua_State *L){
    NdObject *o=check_object(L,1);
    const NdAnim3D *clip=object_anim3d(o);
    if(!clip)return luaL_error(L,"this object has no 3D animation");
    const char *name=luaL_checkstring(L,2);
    if(strcmp(name,clip->name))return luaL_error(L,"unknown animation: %s",name);
    if(!o->anim3d_playing){reset_anim3d(o);o->anim3d_playing=1;}
    return 0;
}
static int lua_object_restart_animation(lua_State *L){
    NdObject *o=check_object(L,1);
    if(!object_anim3d(o))return luaL_error(L,"no 3D animation on this object");
    reset_anim3d(o);o->anim3d_playing=1;return 0;
}
static int lua_object_pause_animation(lua_State *L){
    NdObject *o=check_object(L,1);o->anim3d_playing=0;return 0;
}
static int lua_object_resume_animation(lua_State *L){
    NdObject *o=check_object(L,1);
    if(!object_anim3d(o))return luaL_error(L,"no 3D animation on this object");
    o->anim3d_playing=1;return 0;
}
static int lua_object_stop_animation(lua_State *L){
    NdObject *o=check_object(L,1);o->anim3d_playing=0;reset_anim3d(o);return 0;
}

static int lua_object_play(lua_State *L) {
    NdObject *o=check_object(L,1);
    if(o->def.type==2)o->anim_playing=1;
    return 0;
}
static int lua_object_pause(lua_State *L) {
    NdObject *o=check_object(L,1);
    if(o->def.type==2)o->anim_playing=0;
    return 0;
}
static int lua_object_index(lua_State *L) {
    NdObject *o=check_object(L,1);
    const char *key=luaL_checkstring(L,2);
    if (field_equals(key,"move")) {lua_pushcfunction(L,lua_object_move);return 1;}
    if (field_equals(key,"playAnimation")) {lua_pushcfunction(L,lua_object_play_animation);return 1;}
    if (field_equals(key,"restartAnimation")) {lua_pushcfunction(L,lua_object_restart_animation);return 1;}
    if (field_equals(key,"pauseAnimation")) {lua_pushcfunction(L,lua_object_pause_animation);return 1;}
    if (field_equals(key,"resumeAnimation")) {lua_pushcfunction(L,lua_object_resume_animation);return 1;}
    if (field_equals(key,"stopAnimation")) {lua_pushcfunction(L,lua_object_stop_animation);return 1;}
    if (field_equals(key,"play")) {lua_pushcfunction(L,lua_object_play);return 1;}
    if (field_equals(key,"pause")) {lua_pushcfunction(L,lua_object_pause);return 1;}
    if (push_field(L,o,key))return 1;
    lua_getiuservalue(L,1,1); // custom fields persist in this userdata
    lua_pushvalue(L,2);
    lua_gettable(L,-2);
    return 1;
}
static int lua_object_newindex(lua_State *L) {
    NdObject *o=check_object(L,1);
    const char *key=luaL_checkstring(L,2);
    if (property_set(L,o,key,3))return 0;
    lua_getiuservalue(L,1,1);
    lua_pushvalue(L,2);
    lua_pushvalue(L,3);
    lua_settable(L,-3);
    return 0;
}

/* Register object userdata once in a registry table indexed by scene index. */
static void make_object_userdata(lua_State *L,int scene_index) {
    int *idx=(int*)lua_newuserdatauv(L,sizeof(int),1);
    *idx=scene_index;
    luaL_setmetatable(L,"NovaDS.Object");
    lua_newtable(L);
    lua_setiuservalue(L,-2,1);
}

/* Raycast against active 3D colliders (AABB proxy for spheres). Returns object, distance. */
static int lua_physics3d_raycast(lua_State *L){
    double ox=luaL_checknumber(L,1),oy=luaL_checknumber(L,2),oz=luaL_checknumber(L,3);
    double dx=luaL_checknumber(L,4),dy=luaL_checknumber(L,5),dz=luaL_checknumber(L,6);
    double length=luaL_checknumber(L,7);
    int ignore=luaL_optinteger(L,8,0);
    double norm=sqrt(dx*dx+dy*dy+dz*dz);
    if(!isfinite(norm) || norm<0.000001 || !isfinite(length) || length<=0 || length>100)
        return luaL_error(L,"bad ray direction or range");
    dx/=norm;dy/=norm;dz/=norm;
    double origin[3]={ox,oy,oz},direction[3]={dx,dy,dz};
    int best=-1;double best_distance=length;
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *o=&objects[i];
        if(!active_object(o) || !(o->def.type==1 || o->def.type==3) ||
           !o->collider3d || o->def.id==ignore)continue;
        double center[3]={o->x/65536.0,o->y/65536.0,o->z/65536.0};
        double extents[3]={o->half_x3d/65536.0,o->half_y3d/65536.0,o->half_z3d/65536.0};
        if(o->sphere3d)extents[1]=extents[2]=extents[0];
        double tmin=0,tmax=best_distance;
        int hit=1;
        for(int a=0;a<3;a++){
            double low=center[a]-extents[a],high=center[a]+extents[a];
            if(fabs(direction[a])<0.0000001){if(origin[a]<low || origin[a]>high){hit=0;break;}}
            else {
                double ta=(low-origin[a])/direction[a],tb=(high-origin[a])/direction[a];
                if(ta>tb){double tmp=ta;ta=tb;tb=tmp;}
                if(ta>tmin)tmin=ta;
                if(tb<tmax)tmax=tb;
                if(tmax<tmin){hit=0;break;}
            }
        }
        if(hit && tmin<best_distance){best=i;best_distance=tmin;}
    }
    if(best<0){lua_pushnil(L);return 1;}
    lua_rawgeti(L,LUA_REGISTRYINDEX,object_table_ref);
    lua_rawgeti(L,-1,best+1);
    lua_remove(L,-2);
    lua_pushnumber(L,best_distance);
    return 2;
}

static int lua_camera3_position(lua_State *L) {
    if(!nd_scene.mode_3d2d)return luaL_error(L,"Camera3D needs 3D mode");
    double xyz[3]={luaL_checknumber(L,1),luaL_checknumber(L,2),luaL_checknumber(L,3)};
    for(int i=0;i<3;i++)if(!(xyz[i]>=-24 && xyz[i]<=24))return luaL_error(L,"Camera3D position outside -24..24");
    camera3_x=(int)(xyz[0]*4096);camera3_y=(int)(xyz[1]*4096);camera3_z=(int)(xyz[2]*4096);
    return 0;
}
static int lua_camera3_rotation(lua_State *L) {
    if(!nd_scene.mode_3d2d)return luaL_error(L,"Camera3D needs 3D mode");
    double yaw=luaL_checknumber(L,1),pitch=luaL_checknumber(L,2);
    if(!(yaw>=-3600 && yaw<=3600 && pitch>=-85 && pitch<=85))return luaL_error(L,"invalid camera orientation");
    camera3_yaw=(int)(yaw*(65536.0/360.0));camera3_pitch=(int)(pitch*(65536.0/360.0));return 0;
}
static int lua_camera3_bottom_position(lua_State *L){
    if(!nd_scene.dual3d)return luaL_error(L,"Bottom 3D camera requires Dual 3D");
    double x=luaL_checknumber(L,1),y=luaL_checknumber(L,2),z=luaL_checknumber(L,3);
    if(x<-24||x>24||y<-24||y>24||z<-24||z>24)return luaL_error(L,"Bottom camera position outside -24..24");
    camera_bottom_x=(int)(x*4096);camera_bottom_y=(int)(y*4096);camera_bottom_z=(int)(z*4096);
    return 0;
}
static int lua_camera3_bottom_rotation(lua_State *L){
    if(!nd_scene.dual3d)return luaL_error(L,"Bottom 3D camera requires Dual 3D");
    double yaw=luaL_checknumber(L,1),pitch=luaL_checknumber(L,2);
    if(yaw<-3600||yaw>3600||pitch<-85||pitch>85)return luaL_error(L,"Bottom camera rotation invalid");
    camera_bottom_yaw=(int)(yaw*65536/360);camera_bottom_pitch=(int)(pitch*65536/360);
    return 0;
}
static int lua_input_down(lua_State *L) {
    const char *name=luaL_checkstring(L,1);
    int key=0;
    struct {const char *name;int bit;} k[]={
        {"A",KEY_A},{"B",KEY_B},{"X",KEY_X},{"Y",KEY_Y},
        {"L",KEY_L},{"R",KEY_R},{"UP",KEY_UP},{"DOWN",KEY_DOWN},
        {"LEFT",KEY_LEFT},{"RIGHT",KEY_RIGHT},{"START",KEY_START},
        {"SELECT",KEY_SELECT},{"TOUCH",KEY_TOUCH}};
    for(unsigned int i=0;i<sizeof(k)/sizeof(k[0]);i++)
        if (strcmp(name,k[i].name)==0) {key=k[i].bit;break;}
    lua_pushboolean(L,key && (held_keys&key));
    return 1;
}
static int lua_input_pressed(lua_State *L) {
    const char *name=luaL_checkstring(L,1);
    int key=0;
    struct {const char *name;int bit;} k[]={
        {"A",KEY_A},{"B",KEY_B},{"X",KEY_X},{"Y",KEY_Y},
        {"L",KEY_L},{"R",KEY_R},{"UP",KEY_UP},{"DOWN",KEY_DOWN},
        {"LEFT",KEY_LEFT},{"RIGHT",KEY_RIGHT},{"START",KEY_START},
        {"SELECT",KEY_SELECT},{"TOUCH",KEY_TOUCH}};
    for(unsigned int i=0;i<sizeof(k)/sizeof(k[0]);i++)
        if (strcmp(name,k[i].name)==0) {key=k[i].bit;break;}
    lua_pushboolean(L,key && (pressed_keys&key));
    return 1;
}

/* Object refs stored in Lua registry, keyed by fixed scene index (1-based). */
static int lua_scene_get(lua_State *L) {
    int id=(int)luaL_checkinteger(L,1);
    lua_rawgeti(L,LUA_REGISTRYINDEX,object_table_ref);
    for (int i=0;i<nd_scene.object_count;i++)if (objects[i].def.id==id && active_object(&objects[i])) {
        lua_rawgeti(L,-1,i+1);
        return 1;
    }
    lua_pushnil(L);return 1;
}

/* Lua 2D API: Background.scroll / Background.transform / UI.print. */
/* Scene changes are queued until the next frame. Never mutate the scene while
   Lua callbacks or collision iteration are running. */
static int lua_scene_load(lua_State *L) {
    const char *name=luaL_checkstring(L,1);
    for(int i=0;i<nd_scene.scene_count;i++)if(strcmp(name,nd_scene.scene_names[i])==0){
        requested_scene=i;return 0;
    }
    return luaL_error(L,"unknown scene: %s",name);
}
static int lua_scene_current(lua_State *L) {
    lua_pushstring(L,nd_scene.scene_names[current_scene]);return 1;
}
static int lua_sound_play(lua_State *L) {
    const char *name=luaL_checkstring(L,1);
    int volume=(int)luaL_optinteger(L,2,127);
    int pan=(int)luaL_optinteger(L,3,64);
    bool loop=lua_toboolean(L,4);
    if(volume<0 || volume>127 || pan<0 || pan>127)
        return luaL_error(L,"audio volume/pan range is 0..127");
    for(int i=0;i<nd_scene.sound_count;i++){
        const NdSound *snd=&nd_scene.sounds[i];
        if(strcmp(name,snd->name)==0){
            int channel=soundPlaySample(snd->pcm8,SoundFormat_8Bit,snd->frames,
                                        snd->rate,volume,pan,loop,0);
            lua_pushinteger(L,channel);return 1;
        }
    }
    return luaL_error(L,"unknown sound: %s",name);
}
static int lua_input_touch(lua_State *L) {
    if(touch_x<0){lua_pushnil(L);return 1;}
    lua_pushinteger(L,touch_x);lua_pushinteger(L,touch_y);return 2;
}
static int lua_screen(lua_State *L,int arg) {
    const char *name=luaL_checkstring(L,arg);
    if(strcmp(name,"top")==0)return 0;
    if(strcmp(name,"bottom")==0)return 1;
    return luaL_error(L,"screen must be 'top' or 'bottom'");
}
static NdBgRuntime *lua_find_bg(lua_State *L,int screen,int arg) {
    const char *name=luaL_checkstring(L,arg);
    for(int slot=0;slot<2;slot++) {
        int index=screen*2+slot;
        if(bg_layers[index].id>=0 && nd_scene.backgrounds[index].name &&
           strcmp(nd_scene.backgrounds[index].name,name)==0)return &bg_layers[index];
    }
    luaL_error(L,"unknown layer name");return NULL;
}
static int lua_bg_scroll(lua_State *L) {
    int screen=lua_screen(L,1);
    int arg=2;
    NdBgRuntime *b=&bg_layers[screen*2];
    if(lua_type(L,2)==LUA_TSTRING){b=lua_find_bg(L,screen,2);arg=3;}
    if(b->id<0)return luaL_error(L,"screen has no tile background");
    double x=luaL_checknumber(L,arg),y=luaL_checknumber(L,arg+1);
    if(!(x>=-32768 && x<=32767 && y>=-32768 && y<=32767))
        return luaL_error(L,"background scroll outside allowed range");
    b->x=(int)x;b->y=(int)y;return 0;
}
/* Toggle a scenery layer without changing the project's video mode.
   Useful when several named scenes share background assets. */
static int lua_bg_show(lua_State *L) {
    int screen=lua_screen(L,1);
    NdBgRuntime *b=lua_find_bg(L,screen,2);
    bool visible=lua_toboolean(L,3);
    if(visible)bgShow(b->id);
    else bgHide(b->id);
    return 0;
}
static int lua_bg_transform(lua_State *L) {
    int screen=lua_screen(L,1);
    NdBgRuntime *b=&bg_layers[screen*2];
    if(b->id<0 || !b->affine)return luaL_error(L,"requires affine background");
    double degrees=luaL_checknumber(L,2),scale=luaL_checknumber(L,3);
    if(!(degrees>=-3600 && degrees<=3600 && scale>=0.25 && scale<=4))
        return luaL_error(L,"invalid affine angle/scale");
    b->angle=(int)(degrees*(512.0/360.0));b->scale256=(int)(256.0/scale);return 0;
}
static int lua_camera_set(lua_State *L) {
    int screen=lua_screen(L,1);
    int x=(int)luaL_checkinteger(L,2),y=(int)luaL_checkinteger(L,3);
    if(x < -16384 || x > 16384 || y < -16384 || y > 16384)
        return luaL_error(L,"camera coordinates exceed limit");
    follow_id[screen]=0;camera_x[screen]=x;camera_y[screen]=y;return 0;
}
static int lua_camera_follow(lua_State *L) {
    int screen=lua_screen(L,1);
    int id=(int)luaL_checkinteger(L,2);
    follow_id[screen]=id;return 0;
}
static int lua_ui_print(lua_State *L) {
    int screen=lua_screen(L,1);
    PrintConsole *pc=ui_consoles[screen];
    if(!pc)return luaL_error(L,"text not available on this screen in 3D mode");
    int x=(int)luaL_checkinteger(L,2),y=(int)luaL_checkinteger(L,3);
    size_t len=0;const char *txt=luaL_checklstring(L,4,&len);
    if(x<0 || x>=32 || y<0 || y>=24)return luaL_error(L,"UI text coords out of bounds");
    if(len>(size_t)(32-x))len=32-x;
    PrintConsole *previous=consoleSelect(pc);
    iprintf("\x1b[%d;%dH%.*s",y+1,x+1,(int)len,txt);
    consoleSelect(previous);
    return 0;
}
static int lua_ui_clear(lua_State *L) {
    int screen=lua_screen(L,1);
    PrintConsole *pc=ui_consoles[screen];
    if(!pc)return luaL_error(L,"text not available on this screen in 3D mode");
    PrintConsole *previous=consoleSelect(pc);
    consoleClear();consoleSelect(previous);
    return 0;
}

/* UI widgets use the hardware BG0 console, which is 32x24 characters.
   They require no bitmap framebuffer or additional VRAM. */
static int lua_ui_button(lua_State *L) {
    int screen=lua_screen(L,1);
    PrintConsole *pc=ui_consoles[screen];
    if(!pc)return luaL_error(L,"UI requires a 2D screen");
    int x=(int)luaL_checkinteger(L,2),y=(int)luaL_checkinteger(L,3);
    size_t length=0;const char *label=luaL_checklstring(L,4,&length);
    if(x<0 || x>=30 || y<0 || y>=24)return luaL_error(L,"UI.button outside screen");
    if(length>(size_t)(30-x))length=30-x;
    PrintConsole *last=consoleSelect(pc);
    iprintf("\x1b[%d;%dH[%.*s]",y+1,x+1,(int)length,label);
    consoleSelect(last);
    bool hit=screen==1 && (pressed_keys&KEY_TOUCH) &&
        touch_x>=x*8 && touch_y>=y*8 && touch_x<(x+(int)length+2)*8 && touch_y<(y+1)*8;
    lua_pushboolean(L,hit);return 1;
}
static int lua_ui_bar(lua_State *L) {
    int screen=lua_screen(L,1);PrintConsole *pc=ui_consoles[screen];
    if(!pc)return luaL_error(L,"UI requires a 2D screen");
    int x=(int)luaL_checkinteger(L,2),y=(int)luaL_checkinteger(L,3);
    int width=(int)luaL_checkinteger(L,4);
    double value=luaL_checknumber(L,5),max=luaL_checknumber(L,6);
    if(width<1 || width>29 || x<0 || y<0 || y>=24 || x+width+2>32 ||
       !(max>0) || !(value>=0 && value<=max))return luaL_error(L,"UI.bar invalid parameters");
    int fill=(int)(value*width/max+0.5);
    char bar[33];bar[0]='[';
    for(int i=0;i<width;i++)bar[i+1]=i<fill?'#':'-';
    bar[width+1]=']';bar[width+2]=0;
    PrintConsole *last=consoleSelect(pc);
    iprintf("\x1b[%d;%dH%s",y+1,x+1,bar);consoleSelect(last);return 0;
}
static void open_safelibs(lua_State *L) {
    luaL_requiref(L,"_G",luaopen_base,1);lua_pop(L,1);
    luaL_requiref(L,LUA_TABLIBNAME,luaopen_table,1);lua_pop(L,1);
    luaL_requiref(L,LUA_STRLIBNAME,luaopen_string,1);lua_pop(L,1);
    luaL_requiref(L,LUA_MATHLIBNAME,luaopen_math,1);lua_pop(L,1);
    luaL_requiref(L,LUA_UTF8LIBNAME,luaopen_utf8,1);lua_pop(L,1);
    /* No io, os, debug or package: scripts cannot access files or native libs. */
}

static void init_lua(void) {
    nd_lua=lua_newstate(budget_alloc,NULL);
    if (!nd_lua) {iprintf("\x1b[2;1HLua: out of memory");return;}
    lua_State *L=nd_lua;
    open_safelibs(L);
    lua_sethook(L,vm_hook,LUA_MASKCOUNT,500);
    luaL_newmetatable(L,"NovaDS.Object");
    lua_pushcfunction(L,lua_object_index);lua_setfield(L,-2,"__index");
    lua_pushcfunction(L,lua_object_newindex);lua_setfield(L,-2,"__newindex");
    lua_pop(L,1);
    lua_newtable(L);
    for(int i=0;i<nd_scene.object_count;i++) {
        make_object_userdata(L,i);
        lua_rawseti(L,-2,i+1);
    }
    object_table_ref=luaL_ref(L,LUA_REGISTRYINDEX);
    lua_newtable(L);
    lua_pushcfunction(L,lua_scene_get);lua_setfield(L,-2,"get");
    lua_pushcfunction(L,lua_scene_load);lua_setfield(L,-2,"load");
    lua_pushcfunction(L,lua_scene_current);lua_setfield(L,-2,"current");
    lua_setglobal(L,"Scene");
    lua_newtable(L);
    lua_pushcfunction(L,lua_input_down);lua_setfield(L,-2,"isDown");
    lua_pushcfunction(L,lua_input_down);lua_setfield(L,-2,"IsDown");
    lua_pushcfunction(L,lua_input_pressed);lua_setfield(L,-2,"pressed");
    lua_pushcfunction(L,lua_input_pressed);lua_setfield(L,-2,"Pressed");
    lua_pushcfunction(L,lua_input_touch);lua_setfield(L,-2,"touch");
    lua_setglobal(L,"Input");
    lua_newtable(L);
    lua_pushcfunction(L,lua_bg_scroll);lua_setfield(L,-2,"scroll");
    lua_pushcfunction(L,lua_bg_scroll);lua_setfield(L,-2,"setScroll");
    lua_pushcfunction(L,lua_bg_transform);lua_setfield(L,-2,"transform");
    lua_pushcfunction(L,lua_bg_show);lua_setfield(L,-2,"show");
    lua_setglobal(L,"Background");
    lua_newtable(L);
    lua_pushcfunction(L,lua_camera_set);lua_setfield(L,-2,"set");
    lua_pushcfunction(L,lua_camera_follow);lua_setfield(L,-2,"follow");
    lua_setglobal(L,"Camera");
    lua_newtable(L);
    lua_pushcfunction(L,lua_camera3_position);lua_setfield(L,-2,"setPosition");
    lua_pushcfunction(L,lua_camera3_rotation);lua_setfield(L,-2,"setRotation");
    lua_pushcfunction(L,lua_camera3_bottom_position);lua_setfield(L,-2,"setBottomPosition");
    lua_pushcfunction(L,lua_camera3_bottom_rotation);lua_setfield(L,-2,"setBottomRotation");
    lua_setglobal(L,"Camera3D");
    lua_newtable(L);
    lua_pushcfunction(L,lua_physics3d_raycast);lua_setfield(L,-2,"raycast");
    lua_setglobal(L,"Physics3D");
    lua_newtable(L);
    lua_pushcfunction(L,lua_ui_print);lua_setfield(L,-2,"print");
    lua_pushcfunction(L,lua_ui_clear);lua_setfield(L,-2,"clear");
    lua_pushcfunction(L,lua_ui_button);lua_setfield(L,-2,"button");
    lua_pushcfunction(L,lua_ui_bar);lua_setfield(L,-2,"bar");
    lua_setglobal(L,"UI");
    lua_newtable(L);
    lua_pushcfunction(L,lua_sound_play);lua_setfield(L,-2,"play");
    lua_setglobal(L,"Audio");

    for(int i=0;i<nd_scene.object_count;i++) {
        NdObject *o=&objects[i];int index=o->def.script;
        if (index<0 || index>=nd_scene.script_count)continue;
        const NdScript *src=&nd_scene.scripts[index];
        if (luaL_loadbufferx(L,(const char*)src->source,src->length,src->name,"t")!=LUA_OK) {
            const char *e=lua_tostring(L,-1);
            iprintf("\x1b[2;1H%-31.31s",e ? e : "Lua syntax error");
            lua_pop(L,1);continue;
        }
        /* Environment inherits registered API via _G, but local script
           globals and functions are private per object instance. */
        lua_newtable(L); /* environment */
        lua_newtable(L); /* metatable */
        lua_pushglobaltable(L);lua_setfield(L,-2,"__index");
        lua_setmetatable(L,-2);
        lua_rawgeti(L,LUA_REGISTRYINDEX,object_table_ref);
        lua_rawgeti(L,-1,i+1);
        lua_setfield(L,-3,"self");
        lua_pop(L,1);
        lua_pushvalue(L,-1);
        o->lua_env_ref=luaL_ref(L,LUA_REGISTRYINDEX);
        /* stack [chunk, env]; _ENV upvalue gets env */
        if (!lua_setupvalue(L,-2,1))lua_pop(L,1);
        if (guarded_call(L,0,0)!=LUA_OK) {
            luaL_unref(L,LUA_REGISTRYINDEX,o->lua_env_ref);
            o->lua_env_ref=LUA_NOREF;
        }
    }
}

static void call_lua_event(NdObject *o,const char *event,double dt) {
    if (!nd_lua || o->lua_env_ref==LUA_NOREF)return;
    lua_State *L=nd_lua;
    lua_rawgeti(L,LUA_REGISTRYINDEX,o->lua_env_ref);
    lua_getfield(L,-1,event);
    if (!lua_isfunction(L,-1)) {lua_pop(L,2);return;}
    /* Discard env table beneath callback; keep stack stable. */
    lua_remove(L,-2);
    if (strcmp(event,"Update")==0) {
        lua_pushnumber(L,dt);
        guarded_call(L,1,0);
    } else guarded_call(L,0,0);
}

/* Transform keys are offsets from an object's scripted/base transform.
   Remove LAST frame's offsets first, then apply CURRENT offsets. This means
   scripts can still move a kinematic platform while it animates. */
static int32_t lerp_animated(int32_t a,int32_t b,int fraction256){
    return a+(int32_t)(((int64_t)(b-a)*fraction256)/256);
}
static void step_animations3d(void){
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *o=&objects[i];
        if(!active_object(o) || !o->anim3d_playing)continue;
        const NdAnim3D *a=object_anim3d(o);
        if(!a)continue;
        /* Advance in 8.8 animation frames, no per-frame heap allocations. */
        int increment=(a->fps256*o->anim3d_speed256)/(60*256);
        if(increment<1)increment=1;
        int frame256=o->anim3d_time256;
        const int limit=a->duration*256;
        if(frame256>limit)frame256=limit;
        int dx=0,dy=0,dz=0,yaw=0,scale=256;
        if(a->keys && a->key_count){
            const NdAnimKey3D *lo=&a->keys[0], *hi=lo;
            for(int k=1;k<a->key_count;k++){
                hi=&a->keys[k];
                if(frame256<=hi->frame*256)break;
                lo=hi;
            }
            int t=0;
            if(hi!=lo && hi->frame>lo->frame){
                t=(frame256-lo->frame*256)/(hi->frame-lo->frame);
                if(t<0)t=0;if(t>256)t=256;
            }
            dx=lerp_animated(lo->dx,hi->dx,t);
            dy=lerp_animated(lo->dy,hi->dy,t);
            dz=lerp_animated(lo->dz,hi->dz,t);
            yaw=lerp_animated(lo->yaw,hi->yaw,t);
            scale=lerp_animated(lo->scale256,hi->scale256,t);
        }
        o->x+=dx-o->anim3d_last_x;
        o->y+=dy-o->anim3d_last_y;
        o->z+=dz-o->anim3d_last_z;
        o->angle=(o->angle+yaw-o->anim3d_last_yaw)&65535;
        o->anim3d_last_x=dx;o->anim3d_last_y=dy;o->anim3d_last_z=dz;
        o->anim3d_last_yaw=yaw;o->anim3d_scale256=scale;
        if(a->mesh_frames && a->mesh_frame_count){
            int f=(int)(((int64_t)frame256*a->mesh_frame_count)/(limit+1));
            if(f>=a->mesh_frame_count)f=a->mesh_frame_count-1;
            o->anim3d_mesh=a->mesh_frames[f];
        }
        frame256+=increment;
        if(frame256>limit){
            if(a->loop){frame256=frame256%(limit+1);}
            else{frame256=limit;o->anim3d_playing=0;}
        }
        o->anim3d_time256=frame256;
        if(!o->anim3d_playing && !a->loop)call_lua_event(o,"OnAnimationFinished",0);
    }
}

/* Collision event callbacks receive the OTHER object (Scene.get-compatible userdata). */
static void call_lua_contact(NdObject *o,const char *event,int other) {
    if (!nd_lua || o->lua_env_ref==LUA_NOREF)return;
    lua_State *L=nd_lua;
    lua_rawgeti(L,LUA_REGISTRYINDEX,o->lua_env_ref);
    lua_getfield(L,-1,event);
    if(!lua_isfunction(L,-1)){lua_pop(L,2);return;}
    lua_remove(L,-2);
    lua_rawgeti(L,LUA_REGISTRYINDEX,object_table_ref);
    lua_rawgeti(L,-1,other+1);
    lua_remove(L,-2);
    guarded_call(L,1,0);
}
static void call_lua_tile(NdObject *o,int tx,int ty,const char *layer) {
    if (!nd_lua || o->lua_env_ref==LUA_NOREF)return;
    lua_State *L=nd_lua;
    lua_rawgeti(L,LUA_REGISTRYINDEX,o->lua_env_ref);
    lua_getfield(L,-1,"OnTileCollision");
    if(!lua_isfunction(L,-1)){lua_pop(L,2);return;}
    lua_remove(L,-2);
    lua_pushinteger(L,tx);lua_pushinteger(L,ty);lua_pushstring(L,layer ? layer : "layer");
    guarded_call(L,3,0);
}
static NdPhysRect physics_box(const NdObject *o){
    NdPhysRect r={o->x,o->y,o->collider_w,o->collider_h};
    if((r.w<=0 || r.h<=0) && o->def.image>=0 && o->def.image<nd_scene.image_count){
        const NdImage *im=&nd_scene.images[o->def.image];
        if(r.w<=0)r.w=im->width;
        if(r.h<=0)r.h=im->height;
    }
    if(r.w<=0)r.w=16;
    if(r.h<=0)r.h=16;
    return r;
}
static bool collision_filter(const NdObject *a,const NdObject *b){
    return a->collider && b->collider && a->def.type==2 && b->def.type==2 &&
           a->def.screen==b->def.screen &&
           (a->collision_mask & b->collision_layer) &&
           (b->collision_mask & a->collision_layer);
}
static bool tile_solid(int slot,int x,int y){
    const NdTileCollision *tile=&nd_scene.tile_collisions[slot];
    if(!tile->bits || x<0 || y<0 || x>=tile->width || y>=tile->height)return false;
    int i=y*tile->width+x;
    return (tile->bits[i>>3] & (1<<(i&7)))!=0;
}
static int32_t physics_restrict(NdObject *o,NdPhysRect body,int32_t target,int axis,
                                int *tile_x,int *tile_y,int *tile_slot){
    int32_t allowed=target;
    for(int i=0;i<nd_scene.object_count;i++){
        const NdObject *other=&objects[i];
        if(other==o || !active_object(other) || !other->solid || other->trigger || !collision_filter(o,other))continue;
        int32_t candidate=nd_physics_limit(body,allowed,axis,physics_box(other));
        if(candidate!=allowed)allowed=candidate;
    }
    int screen=o->def.screen;
    /* Only one solid tile callback per movement axis, avoiding event storms. */
    for(int slot=screen*2;slot<screen*2+2;slot++){
        const NdTileCollision *tile=&nd_scene.tile_collisions[slot];
        if(!tile->bits)continue;
        int64_t start=axis?body.y:body.x;
        int64_t low=start<target?start:target;
        int64_t high=(start>target?start:target)+(int64_t)(axis?body.h:body.w)*65536;
        /* Clamp coordinates before scanning, even for teleported sprites. */
        int tile_start=(int)(low/65536/8)-1;
        int tile_end=(int)(high/65536/8)+1;
        if(tile_start<0)tile_start=0;
        int max_axis=axis?tile->height:tile->width;
        if(tile_end>=max_axis)tile_end=max_axis-1;
        int other_start=(int)((axis?body.x:body.y)/65536/8)-1;
        int other_end=(int)(((axis?body.x:body.y)/65536+
                                  (axis?body.w:body.h))/8)+1;
        if(other_start<0)other_start=0;
        int max_other=axis?tile->width:tile->height;
        if(other_end>=max_other)other_end=max_other-1;
        for(int a=tile_start;a<=tile_end;a++)for(int b=other_start;b<=other_end;b++){
            int tx=axis?b:a,ty=axis?a:b;
            if(!tile_solid(slot,tx,ty))continue;
            NdPhysRect wall={(int32_t)(tx*8*65536),(int32_t)(ty*8*65536),8,8};
            int32_t candidate=nd_physics_limit(body,allowed,axis,wall);
            if(candidate!=allowed){
                allowed=candidate;
                if(tile_x && *tile_slot<0){*tile_x=tx;*tile_y=ty;*tile_slot=slot;}
            }
        }
    }
    return allowed;
}
static void step_physics(void){
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *o=&objects[i];
        if(!active_object(o) || o->def.type!=2)continue;
        if(o->physics){
            o->vy+=o->gravity/60;
            if(o->friction>0){
                int32_t amount=o->friction/60;
                if(o->vx>0)o->vx=o->vx>amount?o->vx-amount:0;
                else if(o->vx<0)o->vx=o->vx< -amount?o->vx+amount:0;
            }
        }
        int32_t proposed_x=o->x+(o->physics?o->vx/60:0);
        int32_t proposed_y=o->y+(o->physics?o->vy/60:0);
        o->grounded=0;
        if(o->collider && !o->trigger){
            NdPhysRect start=physics_box(o);
            start.x=o->old_x;start.y=o->old_y;
            int tx=-1,ty=-1,slot=-1;
            int32_t newx=physics_restrict(o,start,proposed_x,0,&tx,&ty,&slot);
            if(newx!=proposed_x)o->vx=0;
            if(slot>=0)call_lua_tile(o,tx,ty,nd_scene.backgrounds[slot].name);
            o->x=newx;
            start.x=o->x;
            slot=-1;
            int32_t newy=physics_restrict(o,start,proposed_y,1,&tx,&ty,&slot);
            if(newy!=proposed_y){
                if(proposed_y>o->old_y)o->grounded=1;
                o->vy=0;
            }
            if(slot>=0)call_lua_tile(o,tx,ty,nd_scene.backgrounds[slot].name);
            o->y=newy;
            /* Contact probe: grounded stays true when standing motionless. */
            if(!o->grounded){
                start=physics_box(o);
                o->grounded=physics_restrict(o,start,o->y+65536,1,NULL,NULL,NULL)!=o->y+65536;
            }
        }else{
            o->x=proposed_x;o->y=proposed_y;
        }
    }
    /* Detect collider contacts AFTER all objects have moved. */
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *a=&objects[i];
        if(!active_object(a) || a->def.type!=2 || !a->collider)continue;
        for(int j=i+1;j<nd_scene.object_count;j++){
            NdObject *b=&objects[j];
            bool touching=active_object(b) && collision_filter(a,b) && nd_physics_touch(physics_box(a),physics_box(b));
            bool before=previous_contacts[i][j]!=0;
            previous_contacts[i][j]=touching;
            if(touching && !before){
                call_lua_contact(a,"OnCollisionEnter",j);
                call_lua_contact(b,"OnCollisionEnter",i);
            }else if(touching){
                call_lua_contact(a,"OnCollisionStay",j);
                call_lua_contact(b,"OnCollisionStay",i);
            }else if(before){
                call_lua_contact(a,"OnCollisionExit",j);
                call_lua_contact(b,"OnCollisionExit",i);
            }
        }
    }
}

/* --------- 3D physics: world Y up, all positions 16.16 --------- */
static int is_object3d(const NdObject *o){return o->def.type==1 || o->def.type==3;}
static NdBox3 body3d(const NdObject *o){
    NdBox3 b={o->x,o->y,o->z,o->half_x3d,o->half_y3d,o->half_z3d};
    if(o->sphere3d)b.hy=b.hz=b.hx; /* broad-phase bounding cube */
    return b;
}
static int collision_filter3d(const NdObject *a,const NdObject *b){
    return a->collider3d && b->collider3d &&
           (a->mask3d&b->layer3d) && (b->mask3d&a->layer3d);
}
static int32_t collide_axis3d(NdObject *a,int32_t target,int axis){
    NdBox3 body=body3d(a);
    for(int j=0;j<nd_scene.object_count;j++){
        NdObject *b=&objects[j];
        if(a==b || !active_object(b) || !is_object3d(b) || !b->solid3d ||
           !collision_filter3d(a,b))continue;
        target=nd3d_limit(body,target,axis,body3d(b));
    }
    return target;
}
static int32_t friction3d(int32_t v,int32_t friction){
    int32_t f=friction/60;
    if(v>f)return v-f;
    if(v< -f)return v+f;
    return 0;
}
static void step_physics3d(void){
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *o=&objects[i];
        if(!active_object(o) || !is_object3d(o))continue;
        o->grounded3d=0;
        if(!o->physics3d)continue;
        o->vy+=o->gravity/60;
        if(o->friction>0){o->vx=friction3d(o->vx,o->friction);o->vz=friction3d(o->vz,o->friction);}
        /* Axis separated swept AABB; prevents simple high-speed tunneling. */
        int32_t intended=o->x+o->vx/60;
        if(o->collider3d && !o->trigger3d){
            int32_t limited=collide_axis3d(o,intended,0);
            if(limited!=intended)o->vx=0;
            o->x=limited;
        }else o->x=intended;
        intended=o->y+o->vy/60;
        if(o->collider3d && !o->trigger3d){
            int32_t limited=collide_axis3d(o,intended,1);
            if(limited!=intended){if(intended<o->y)o->grounded3d=1;o->vy=0;}
            o->y=limited;
        }else o->y=intended;
        intended=o->z+o->vz/60;
        if(o->collider3d && !o->trigger3d){
            int32_t limited=collide_axis3d(o,intended,2);
            if(limited!=intended)o->vz=0;
            o->z=limited;
            if(!o->grounded3d && collide_axis3d(o,o->y-256,1)!=o->y-256)
                o->grounded3d=1;
        }else o->z=intended;
    }
    for(int i=0;i<nd_scene.object_count;i++){
        NdObject *a=&objects[i];
        if(!active_object(a) || !is_object3d(a) || !a->collider3d)continue;
        for(int j=i+1;j<nd_scene.object_count;j++){
            NdObject *b=&objects[j];
            int touching=active_object(b) && is_object3d(b) && collision_filter3d(a,b) &&
               nd3d_overlap(body3d(a),a->sphere3d,body3d(b),b->sphere3d);
            int before=previous_contacts[i][j]!=0;
            previous_contacts[i][j]=touching;
            if(touching && !before){call_lua_contact(a,"OnCollisionEnter",j);call_lua_contact(b,"OnCollisionEnter",i);}
            else if(touching){call_lua_contact(a,"OnCollisionStay",j);call_lua_contact(b,"OnCollisionStay",i);}
            else if(before){call_lua_contact(a,"OnCollisionExit",j);call_lua_contact(b,"OnCollisionExit",i);}
        }
    }
}

static void tick_objects(int keys,int pressed) {
    held_keys=keys;pressed_keys=pressed;
    touchPosition touch;
    bool touching=(keys & KEY_TOUCH)!=0;
    if (touching) touchRead(&touch);
    touch_x=touching?touch.px:-1;touch_y=touching?touch.py:-1;
    bool touch_used=false;
    for (int i=0;i<nd_scene.object_count;i++) {
        NdObject *o=&objects[i];NdObjectDef *d=&o->def;
        if(!active_object(o))continue;
        o->old_x=o->x;o->old_y=o->y;
        if (d->type==1 || d->type==3) o->angle=(o->angle+d->spin)&65535;
        else if (d->type==2 && d->controllable && d->script<0) {
            if (keys&KEY_LEFT) o->x-=d->speed*65536;
            if (keys&KEY_RIGHT)o->x+=d->speed*65536;
            if (keys&KEY_UP)   o->y-=d->speed*65536;
            if (keys&KEY_DOWN) o->y+=d->speed*65536;
            if (!touch_used && touching && d->screen==1 && d->image>=0 &&
                d->image<nd_scene.image_count) {
                const NdImage *im=&nd_scene.images[d->image];
                o->x=(touch.px-im->width/2)*65536;
                o->y=(touch.py-im->height/2)*65536;
                touch_used=true;
            }
        }
        call_lua_event(o,"Update",1.0/60.0);
        o->angle&=65535;
        if (d->type==2 && o->anim_playing && o->fps256>0 && d->frame_count>1) {
            o->anim_clock+=o->fps256;
            while(o->anim_clock>=60*256) {
                o->anim_clock-=60*256;
                if(o->frame+1<d->frame_count)o->frame++;
                else if(o->anim_loop)o->frame=0;
                else {o->frame=d->frame_count-1;o->anim_playing=0;break;}
            }
        }
        if (d->type==2 && d->image>=0 && d->image<nd_scene.image_count) {
            const NdImage *im=&nd_scene.images[d->image];
            int maxx=256-im->width,maxy=192-im->height;
            if(follow_id[d->screen]!=0 || o->collider || o->physics)continue; /* world-space movement */
            if (o->x<0)o->x=0;
            if (o->y<0)o->y=0;
            if (o->x>maxx*65536)o->x=maxx*65536;
            if (o->y>maxy*65536)o->y=maxy*65536;
        }
    }
    if (nd_lua)lua_gc(nd_lua,LUA_GCSTEP,8);
}

/* View-sphere culling is deliberately conservative: camera-space sphere
   against near/far and horizontal/vertical FOV, with a small margin. We only
   skip drawing: collision and Lua updates are ALWAYS performed. */
typedef struct {float sy,cy,sp,cp,tanhalf;} NdView;
static NdView view_setup(int fov){
    /* Avoid libm trigonometry every frame when the Lua camera is stationary. */
    static int old_yaw=INT_MIN,old_pitch=INT_MIN,old_fov=INT_MIN;
    static NdView cached;
    if(old_yaw==camera3_yaw && old_pitch==camera3_pitch && old_fov==fov)
        return cached;
    NdView v;
    float yaw=(float)camera3_yaw*(6.28318530718f/65536.0f);
    float pitch=(float)camera3_pitch*(6.28318530718f/65536.0f);
    v.sy=sinf(yaw);v.cy=cosf(yaw);
    v.sp=sinf(pitch);v.cp=cosf(pitch);
    v.tanhalf=tanf(fov*0.00872664626f);
    old_yaw=camera3_yaw;old_pitch=camera3_pitch;old_fov=fov;
    cached=v;
    return v;
}
static float depth3d(const NdObject *o,const NdView *v,float *side,float *up){
    float dx=o->x/65536.0f-camera3_x/4096.0f;
    float dy=o->y/65536.0f-camera3_y/4096.0f;
    float dz=o->z/65536.0f-camera3_z/4096.0f;
    float cx=v->cy*dx-v->sy*dz;
    float cz=v->sy*dx+v->cy*dz;
    *side=cx;*up=v->cp*dy+v->sp*cz;
    return v->sp*dy-v->cp*cz;
}
static float bound3d(const NdObject *o){
    float scale=(o->def.scale/4096.0f)*(o->anim3d_scale256/256.0f);
    int index=o->anim3d_mesh>=0?o->anim3d_mesh:o->def.mesh_index;
    float model_radius=1.74f; /* cube corners */
    if(o->def.type==3 && index>=0 && index<nd_scene.mesh_count)
        model_radius=nd_scene.meshes[index].radius12/4096.0f;
    /* allow for per-object source rotation, plus a slight guard band */
    return fabsf(scale)*model_radius+0.10f;
}
static int sphere_visible(float depth,float x,float y,float radius,const NdView *v){
    if(depth+radius<0.1f || depth-radius>50.0f)return 0;
    if(depth<0.01f)return 1; /* straddles near clip; let GPU decide */
    float h=depth*v->tanhalf+radius*1.5f;
    float w=depth*v->tanhalf*(256.0f/192.0f)+radius*1.5f;
    return fabsf(x)<=w && fabsf(y)<=h;
}
static int stat_seen=0,stat_drawn=0,stat_culled=0,stat_lod=0,stat_tris=0;
static void render_3d_screen(int active_screen) {
    if (!nd_scene.mode_3d2d) return;
    int saved_x=camera3_x,saved_y=camera3_y,saved_z=camera3_z;
    int saved_yaw=camera3_yaw,saved_pitch=camera3_pitch;
    if(nd_scene.dual3d && active_screen==1){
        camera3_x=camera_bottom_x;camera3_y=camera_bottom_y;
        camera3_z=camera_bottom_z;camera3_yaw=camera_bottom_yaw;
        camera3_pitch=camera_bottom_pitch;
    }
    if(nd_scene.dual3d){
        glMatrixMode(GL_PROJECTION);glLoadIdentity();
        gluPerspective(active_screen?nd_scene.camera_bottom_fov:nd_scene.camera_fov,
                       256.0f/192.0f,0.1f,50.0f);
    }
    NdView view=view_setup(nd_scene.dual3d && active_screen==1 ? nd_scene.camera_bottom_fov : nd_scene.camera_fov);
    stat_seen=stat_drawn=stat_culled=stat_lod=stat_tris=0;
    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();
    glRotateXi(-camera3_pitch);
    glRotateYi(-camera3_yaw);
    glTranslatef32(-camera3_x,-camera3_y,-camera3_z);
    for (int i=0;i<nd_scene.object_count;i++){
        NdObject *o=&objects[i];
        if(!active_object(o) || !o->visible || !is_object3d(o) ||
           (nd_scene.dual3d && o->def.screen!=active_screen))continue;
        stat_seen++;
        float side,up;
        float depth=depth3d(o,&view,&side,&up);
        if(nd_scene.frustum_culling && o->def.cull3d &&
           !sphere_visible(depth,side,up,bound3d(o),&view)){
            stat_culled++;continue;
        }
        stat_drawn++;
        if(o->def.type==1){draw_cube(o);stat_tris+=12;}
        else{
            int index=o->anim3d_mesh>=0?o->anim3d_mesh:o->def.mesh_index;
            if(o->def.lod_mesh_index>=0 && o->anim3d_mesh<0 &&
               depth>o->def.lod_distance16/65536.0f){
                index=o->def.lod_mesh_index;stat_lod++;
            }
            if(index>=0 && index<nd_scene.mesh_count){
                stat_tris+=nd_scene.meshes[index].face_count;
                draw_mesh(o,index);
            }
        }
    }
    glFlush(0);
    camera3_x=saved_x;camera3_y=saved_y;camera3_z=saved_z;
    camera3_yaw=saved_yaw;camera3_pitch=saved_pitch;
}

static void render_3d(void) {render_3d_screen(0);}

static void update_camera_follow(void) {
    for(int screen=0;screen<2;screen++) {
        if(!follow_id[screen])continue;
        for(int i=0;i<nd_scene.object_count;i++) {
            NdObject *o=&objects[i];
            if(active_object(o) && o->def.id==follow_id[screen] && o->def.screen==screen && o->def.type==2) {
                camera_x[screen]=(o->x>>16)-120;
                camera_y[screen]=(o->y>>16)-88;
                break;
            }
        }
    }
}
static void render_sprites(void) {
    int matrix_used[2]={0,0};
    for (int i=0;i<nd_scene.object_count;i++) {
        NdObject *o=&objects[i];NdObjectDef *d=&o->def;
        if (d->type!=2 || !o->gfx || o->oam_id<0)continue;
        if(!active_object(o)){
            /* This OAM entry might have been affine in the previous scene.
               The legacy hide helper ASSERTS for affine sprites on libnds.
               Clearing ATTR0 disables either kind safely. */
            oamClearSprite(d->screen?&oamSub:&oamMain,o->oam_id);
            continue;
        }
        int screen=d->screen,asset=d->image+o->frame;
        if(asset<0 || asset>=nd_scene.image_count)continue;
        const NdImage *im=&nd_scene.images[asset];
        const u16 *frame_gfx=image_gfx[screen][asset];
        OamState *oam=screen ? &oamSub : &oamMain;
        int x=(o->x>>16)-camera_x[screen],y=(o->y>>16)-camera_y[screen];
        bool need_affine=(o->angle!=0 || o->scale_x256!=256 || o->scale_y256!=256);
        int matrix=-1;
        bool doubled=false;
        if(need_affine && matrix_used[screen]<32) {
            matrix=matrix_used[screen]++;
            int sx=(256*256)/o->scale_x256;
            int sy=(256*256)/o->scale_y256;
            /* Flips in affine mode must be encoded as negative matrix scales. */
            if(o->flip_x)sx=-sx;
            if(o->flip_y)sy=-sy;
            oamRotateScale(oam,matrix,(s16)o->angle,sx,sy);
            doubled=true;
            /* Doubled affine canvas expands to 2x size around the same center. */
            x-=im->width/2;y-=im->height/2;
        }
        /* If 32 matrices are exhausted, draw as ordinary flipped OAM sprite. */
        oamSet(oam,o->oam_id,x,y,0,o->palette_bank,
               image_size(im),SpriteColorFormat_16Color,frame_gfx,
               matrix,doubled,!o->visible,o->flip_x,o->flip_y,false);
    }
    oamUpdate(&oamSub);oamUpdate(&oamMain);
}

static void perform_scene_change(void) {
    if(requested_scene<0 || requested_scene==current_scene)return;
    current_scene=requested_scene;requested_scene=-1;
    memset(previous_contacts,0,sizeof(previous_contacts));
    camera_x[0]=camera_x[1]=camera_y[0]=camera_y[1]=0;
    camera3_x=nd_scene.camera_x;camera3_y=nd_scene.camera_y;camera3_z=nd_scene.camera_z;
    camera3_yaw=nd_scene.camera_yaw;camera3_pitch=nd_scene.camera_pitch;
    follow_id[0]=nd_scene.follow_top;follow_id[1]=nd_scene.follow_bottom;
    for(int i=0;i<2;i++)if(ui_consoles[i]){
        PrintConsole *last=consoleSelect(ui_consoles[i]);
        consoleClear();consoleSelect(last);
    }
    for(int i=0;i<nd_scene.object_count;i++)if(active_object(&objects[i])){
        NdObject *o=&objects[i];
        reset_anim3d(o);
        o->anim3d_speed256=256;
        const NdAnim3D *a=object_anim3d(o);
        o->anim3d_playing=a ? a->autoplay : 0;
        /* v1.0: restore mutable gameplay state whenever a level is re-entered.
           Pickups may disable their own colliders, physics, or visibility in Lua. */
        o->visible=true;
        o->collider=o->def.collider;o->solid=o->def.solid;
        o->trigger=o->def.trigger;o->physics=o->def.physics;
        o->collision_layer=o->def.collision_layer;
        o->collision_mask=o->def.collision_mask;
        o->collider3d=o->def.collision3d;o->solid3d=o->def.solid3d;
        o->trigger3d=o->def.trigger3d;o->physics3d=o->def.physics3d;
        o->sphere3d=o->def.sphere3d;
        o->layer3d=o->def.collision_layer3d;o->mask3d=o->def.collision_mask3d;
        o->vx=o->def.velocity_x16;o->vy=o->def.velocity_y16;
        o->gravity=o->def.gravity16;o->friction=o->def.friction16;
        o->grounded=0;o->frame=o->def.initial_frame;
        o->anim_playing=o->def.fps256>0;
        o->angle=(o->def.type==2 ? o->def.sprite_angle : o->def.rotation_y);
        o->flip_x=o->def.flip_x;o->flip_y=o->def.flip_y;
        o->fps256=o->def.fps256;o->scale_x256=o->def.scale_x256;
        o->scale_y256=o->def.scale_y256;o->anim_loop=o->def.loop;
        o->grounded3d=0;
        if(is_object3d(o)){
            o->vx=o->def.velocity_x3d;o->vy=o->def.velocity_y3d;o->vz=o->def.velocity_z3d;
            o->gravity=o->def.gravity3d;o->friction=o->def.friction3d;
        }
        o->x=(o->def.type!=2 ? o->def.x*16 : o->def.x*65536);
        o->y=(o->def.type!=2 ? o->def.y*16 : o->def.y*65536);
        o->z=(o->def.type!=2 ? o->def.z*16 : 0);
        o->old_x=o->x;o->old_y=o->y;
        call_lua_event(o,"Start",0);
    }
}

int main(void) {
    current_scene=nd_scene.starting_scene;
    soundEnable();
    init_2d_video();
    load_scene();
    init_lua();
    for (int i=0;i<nd_scene.object_count;i++)if(active_object(&objects[i]))call_lua_event(&objects[i],"Start",0);
    while(pmMainLoop()) {
        scanKeys();
        if (keysDown()&KEY_START)break;
        perform_scene_change();
        tick_objects(keysHeld(),keysDown());
        step_animations3d();
        step_physics();
        step_physics3d();
        update_camera_follow();
        if(nd_scene.dual3d){
            swiWaitForVBlank();
            dual3d_begin_frame(dual3d_phase);
            render_3d_screen(dual3d_phase);
            dual3d_phase^=1;
        }else{
            render_3d();
            swiWaitForVBlank();
            update_backgrounds();
            render_sprites();
        }
        if(nd_scene.profiler && nd_scene.mode_3d2d && !nd_scene.dual3d && (keysHeld()&KEY_SELECT)){
            PrintConsole *last=consoleSelect(&ui_bottom);
            iprintf("\x1b[0;0H3D O:%3d DRAW:%3d CULL:%3d \x1b[1;0HTRI:%4d LOD:%3d          ",
                    stat_seen,stat_drawn,stat_culled,stat_tris,stat_lod);
            consoleSelect(last);
        }
    }
    if (nd_lua)lua_close(nd_lua);
    return 0;
}
