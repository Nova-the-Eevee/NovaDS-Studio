-- Full Lua 5.4! Unlike v0.3, local variables, functions, and tables work.
local speed = 90
local coins = {"red", "blue", "green"}
local step_count = 0

local function move_axis(dt)
    local dx, dy = 0, 0
    if Input.isDown("LEFT")  then dx = dx - 1 end
    if Input.isDown("RIGHT") then dx = dx + 1 end
    if Input.isDown("UP")    then dy = dy - 1 end
    if Input.isDown("DOWN")  then dy = dy + 1 end
    self:move(dx * speed * dt, dy * speed * dt)
end

function Start()
    self.health = 3            -- custom field stored on the object
    self.coins = #coins        -- regular Lua tables/arrays
    self.visible = true
end

function Update(dt)
    move_axis(dt)
    step_count = step_count + 1
    if Input.pressed("B") then
        self.visible = not self.visible
    end
    if Input.pressed("X") then
        self.health = self.health + 1
        speed = math.min(180, speed + 10)
    end
    if Input.pressed("A") then
        -- Another object's live fields are accessible via Scene.get(id).
        local star = Scene.get(4)
        if star then star.y = 52 end
    end
end
