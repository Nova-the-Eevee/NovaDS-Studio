function Start()
    Camera3D.setPosition(0,1.5,5.0)
    Camera3D.setRotation(0,-7)
    UI.clear("bottom")
    UI.print("bottom",2,3,"OOPS! NOVA GOT BONKED")
    UI.print("bottom",2,6,"THOSE RED CUBES HURT!")
    UI.print("bottom",2,9,"THAT WAS A CLOSE ONE.")
    UI.print("bottom",2,15,"A / TOUCH: RETRY")
    UI.print("bottom",2,18,"B: TITLE")
end
function Update(dt)
    if Input.pressed("A") or UI.button("bottom",2,16,"[ RETRY ]") then Scene.load("Level") end
    if Input.pressed("B") then Scene.load("Title") end
end
