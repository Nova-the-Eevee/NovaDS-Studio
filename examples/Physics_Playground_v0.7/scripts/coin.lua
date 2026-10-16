local timer=0
function Update(dt)
    timer=timer+dt
    self.angle=math.sin(timer*2)*12
end
