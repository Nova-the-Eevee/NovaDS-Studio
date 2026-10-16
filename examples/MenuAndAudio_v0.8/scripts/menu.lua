function Start()
    UI.clear("bottom")
    UI.print("bottom",3,2,"NOVADS STUDIO v0.8")
    UI.print("bottom",3,4,"TOUCH PLAY or press A")
end

function Update(dt)
    if UI.button("bottom",3,7,"PLAY") or Input.pressed("A") then
        Audio.play("select")
        Scene.load("Game")
    end
end
