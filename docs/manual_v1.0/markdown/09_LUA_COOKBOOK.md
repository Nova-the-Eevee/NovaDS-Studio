# Lua cookbook — Short working recipes

Each snippet uses the **v1.0 Lua API**. Attach to a suitable object and set its physics/collider properties in the inspector when required. If a snippet refers to an asset/scene or object ID, create it first.

## A. Move a 2D sprite in four directions

```lua
local speed = 100
function Update(dt)
    if Input.isDown("LEFT") then self.x = self.x - speed * dt end
    if Input.isDown("RIGHT") then self.x = self.x + speed * dt end
    if Input.isDown("UP") then self.y = self.y - speed * dt end
    if Input.isDown("DOWN") then self.y = self.y + speed * dt end
end
```

## B. Animate and face the direction of travel

For a Sprite2D with a multi-frame sprite sheet and valid FPS:

```lua
function Start()
    self.fps = 8
    self.loop = true
    self:play()
end
function Update(dt)
    if Input.isDown("LEFT") then self.flipX = true end
    if Input.isDown("RIGHT") then self.flipX = false end
    if Input.pressed("B") then self:pause() end
    if Input.pressed("X") then self:play() end
end
```

## C. A 2D platformer character

```lua
local speed = 110
function Start()
    self.collider, self.physics = true, true
    self.gravity = 550
end
function Update(dt)
    self.vx = 0
    if Input.isDown("LEFT") then self.vx = -speed end
    if Input.isDown("RIGHT") then self.vx = speed end
    if Input.pressed("A") and self.grounded then self.vy = -245 end
end
```

Mark floor tiles solid or create an object with `solid=true` and a collider.

## D. Collect a trigger object

Create a trigger with object **ID 12** in the same scene. Put this script on the player:

```lua
local score = 0
function OnCollisionEnter(other)
    if other.id == 12 and other.collider then
        score = score + 1
        other.visible = false
        other.collider = false
        UI.print("bottom", 1, 1, "SCORE: " .. score)
    end
end
```

It works only when both objects are configured with appropriate colliders and overlapping collision masks/layers.

## E. Touchable title menu

Create named scenes `Title` and `Game`, and attach this script to an object in `Title`:

```lua
function Start()
    UI.clear("bottom")
    UI.print("bottom", 2, 3, "MY DS GAME")
end
function Update(dt)
    if Input.pressed("A") or UI.button("bottom", 2, 10, "PLAY") then
        Scene.load("Game")
    end
end
```

## F. A sound effect

Import a WAV and name it `select`, then:

```lua
if Input.pressed("A") then
    Audio.play("select", 100, 64, false)
end
```

Use inside an `Update(dt)` function, not as free-floating code, unless you want it to play once when the script loads.

## G. Camera following a 2D sprite

```lua
function Start()
    Camera.follow("bottom", self.id)
end
```

Add larger tilemaps and adjust parallax in the layer settings to see the camera scroll.

## H. 3D controller with jump

```lua
local speed = 3
function Start()
    self.collider = true
    self.physics = true
    self.gravity = -12
end
function Update(dt)
    self.vx, self.vz = 0, 0
    if Input.isDown("LEFT") then self.vx = -speed end
    if Input.isDown("RIGHT") then self.vx = speed end
    if Input.isDown("UP") then self.vz = -speed end
    if Input.isDown("DOWN") then self.vz = speed end
    if Input.pressed("A") and self.grounded then self.vy = 5.5 end
end
```

Note the **opposite gravity sign** compared with 2D because 3D Y points upward.

## I. Follow a 3D player with the camera

```lua
function Update(dt)
    Camera3D.setPosition(self.x, self.y + 2.5, self.z + 5)
    Camera3D.setRotation(0, -15)
end
```

The camera is not a mesh object; these functions directly control the hardware scene camera.

## J. Inspect the floor with a ray

```lua
function Update(dt)
    if Input.pressed("Y") then
        local hit, distance = Physics3D.raycast(
            self.x, self.y, self.z,
            0, -1, 0, 10, self.id)
        if hit then
            UI.print("bottom", 1, 14, "HIT #" .. hit.id)
        else
            UI.print("bottom", 1, 14, "NOTHING BELOW")
        end
    end
end
```

## K. Change 3D animation speed

Put a clip named `Bounce` on a 3D object using the timeline:

```lua
function Start()
    self:playAnimation("Bounce")
end
function Update(dt)
    if Input.pressed("X") then self.animationSpeed = 2.0 end
    if Input.pressed("B") then self:restartAnimation() end
end
```

## L. A cross-scene record

If you need a value on the victory screen, the base Lua global table can store a simple value across active-script environments:

```lua
-- In the level's player script, when winning:
_G.LastScore = 3
Scene.load("Win")

-- In a script attached to the Win scene:
function Start()
    UI.print("bottom", 1, 5, "SCORE: " .. tostring(_G.LastScore or 0))
end
```

For scene restart state, clear/reset values explicitly in your `Start()` callback; v1.0 does not implement persistent save files.
