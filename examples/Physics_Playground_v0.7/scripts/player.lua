-- Full Lua 5.4: movement, jumping, solid tile collision and triggers.
local speed = 110
local jump_speed = -245
local coins = 0

function Start()
    self.physics = true
    self.collider = true
    UI.print("bottom", 1, 1, "D-PAD: MOVE  A: JUMP")
end

function Update(dt)
    self.vx = 0
    if Input.isDown("LEFT") then
        self.vx = -speed
        self.flipX = true
    end
    if Input.isDown("RIGHT") then
        self.vx = speed
        self.flipX = false
    end
    if Input.pressed("A") and self.grounded then
        self.vy = jump_speed
    end
end

function OnCollisionEnter(other)
    if other.id == 2 and other.collider then
        coins = coins + 1
        other.visible = false
        other.collider = false
        UI.print("bottom", 1, 3, "COINS: " .. coins .. " ")
    end
end

function OnTileCollision(tx, ty, layer)
    -- Called when X/Y movement is blocked by a solid map tile.
    -- The collision solver handles the stopping automatically.
end
