-- Example of independently maintained local state for an object.
local elapsed = 0
local positions = {44, 52, 60, 52}
local current = 1

function Update(dt)
    elapsed = elapsed + dt
    if elapsed >= 0.5 then
        elapsed = elapsed - 0.5
        current = current % #positions + 1
        self.x = positions[current]
    end
end
