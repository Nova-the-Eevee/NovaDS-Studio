local t = 0
local base_y = 52
function Update(dt)
    t = t + dt
    -- Lua's math library: sin is not part of the old v0.3 language.
    self.y = base_y + 12 * math.sin(t * 2.5)
end
