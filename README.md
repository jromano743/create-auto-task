# Create auto task

_Create auto task_ is a set of scripts that save, format, and generate a python code using **pyautogui** to replicate a process. You can do any task just once and then have python code that replicates the same task.

## Installation
1. Clone this repository using:
~~~
git clone https://github.com/jromano743/create-auto-task.git
~~~

2. Locate in the folder project and create a virtual environment.
~~~
cd create-auto-desk
virtualenv venv
/venv/Scripts/activate
~~~

3. Install the requirements.
~~~
pip install -r requirements.txt
~~~

4. Run the "record.py" file and do your tasks. Then press "esc" two times to stop record. The "interactions.json" file will be generated.

5. With interaction.json file generated , run the "generate_code.py" file.

6. The "generated_file.py" file will generate a new file with the name your given. That file will have the **pyautogui** code to replicate the task.

7. In your generated code you can modify the duration between movements of mouse.