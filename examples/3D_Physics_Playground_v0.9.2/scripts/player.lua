-- NovaDS Studio v0.9.2 real Lua 3D physics sample
-- Movement in world units per second; positive Y is UP.
local speed = 3.0
local jump = 6.0
local collected = 0

function Start()
    self.physics = true
    self.collider = true
    self.gravity = -13.0
    UI.clear("bottom")
    UI.print("bottom", 1, 1, "3D PHYSICS PLAYGROUND")
    UI.print("bottom", 1, 3, "D-PAD: MOVE  A: JUMP")
    UI.print("bottom", 1, 4, "Y: RAYCAST DOWN")
    UI.print("bottom", 1, 6, "WALK THROUGH YELLOW CUBE")
    UI.print("bottom", 1, 8, "GROUNDED: 0")
end

function Update(dt)
    -- IMPORTANT: no hardcoded player controller in the C runtime.
    self.vx, self.vz = 0, 0
    if Input.isDown("LEFT") then self.vx = -speed end
    if Input.isDown("RIGHT") then self.vx = speed end
    if Input.isDown("UP") then self.vz = -speed end
    if Input.isDown("DOWN") then self.vz = speed end
    if Input.pressed("A") and self.grounded then
        self.vy = jump
    end
    -- A third-person camera follows the player along +Z.
    Camera3D.setPosition(self.x, self.y + 2.5, self.z + 6.5)
    Camera3D.setRotation(0, -12)
    if self.grounded then
        UI.print("bottom", 12, 8, "YES")
    else
        UI.print("bottom", 12, 8, "NO ")
    end
    if Input.pressed("Y") then
        local hit, distance = Physics3D.raycast(
            self.x, self.y, self.z, 0, -1, 0, 12, self.id)
        if hit then
            UI.print("bottom", 1, 11, "RAY HIT ID " .. hit.id .. "     ")
        else
            UI.print("bottom", 1, 11, "RAY: NOTHING           ")
        end
    end
end

function OnCollisionEnter(other)
    if other.id == 10 and other.collider then
        other.visible = false
        other.collider = false
        collected = collected + 1
        UI.print("bottom", 1, 13, "TRIGGER PICKED UP! " .. collected)
    end
end
