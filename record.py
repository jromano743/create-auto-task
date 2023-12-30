import os
import pyautogui
import keyboard
import json
from pynput import mouse

interactions = []
isTerminate = False
file_name = 'interactions.json'
running = True

#file
def save_file():
    global interactions
    with open(os.path.join('.','interactions',file_name), 'w') as json_file:
        json.dump(interactions, json_file)

#interactions
def save_mouse_interaction(mouse_pos, mouse_clic):
    interactions.append((mouse_pos.x, mouse_pos.y))
    interactions.append((mouse_clic))

def save_key_intaraction(key_code):
    interactions.append(key_code)

#events
def on_key_press(event):
    global isTerminate
    global running
    
    if event.name == "esc" and not isTerminate:
        isTerminate = True
        return
    elif event.name == "esc" and isTerminate:
        save_file()
        running = False
        return
    
    save_key_intaraction(event.name)
    isTerminate = False
    

def capture_input():
    keyboard.on_press(on_key_press)
    global running
    while running:
        with mouse.Events() as events:
            for event in events:
                if isinstance(event, mouse.Events.Click):
                    if event.button == mouse.Button.left and event.pressed:
                        save_mouse_interaction(pyautogui.position(), 'LC')
                    if event.button == mouse.Button.right and event.pressed:
                        save_mouse_interaction(pyautogui.position(), 'RC')
                
                if not running:
                    break

def run():
    print("Leyendo teclado...")
    capture_input()
    print("Archivo 'interactions.json' generado.")

if __name__ == '__main__':
    interactions = []
    run()