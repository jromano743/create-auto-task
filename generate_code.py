import os
import json

file_name = 'interactions.json'
save_file_name = ''

def save_file(code):
    with open(os.path.join(".","generatedcodes", f"{save_file_name}.py"), 'w+') as code_file:
        code_file.write(code)

def load_file():
    global interactions
    with open(os.path.join('.','interactions',file_name), 'r') as json_file:
        interactions = json.load(json_file)

    code = 'import pyautogui\n\nduration = 1\n\n'
    for interaction in interactions:
        
        #Mouse position
        if type(interaction) == list:
            code += f"pyautogui.moveTo({interaction[0]},{interaction[1]}, duration=duration)\n"
        
        #Keyboard inputs & clicks
        if type(interaction) == str:
            if interaction == 'LC':
                code += 'pyautogui.leftClick()\n'
            elif interaction == 'RC':
                code += 'pyautogui.rightClick()\n'
            else:
                code += f"pyautogui.press('{interaction}')\n"
    
    save_file(code)
    print(f"Archivo {code_name}.py creado exitosamente.")

        

def run(code_name):
    global save_file_name
    save_file_name = code_name
    load_file()

if __name__ == '__main__':
    code_name = input('Enter file name to code: ')
    print(f"Generando archivo {code_name}.py ...")

    run(code_name)