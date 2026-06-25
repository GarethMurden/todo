from datetime import datetime
import os
import sqlite3
from textual.containers import Container
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView

dirname, scriptname = os.path.split(os.path.abspath(__file__))
THIS_DIRECTORY = f'{dirname}{os.sep}'

class ToDo(App):
    '''Terminal to do list'''
    BINDINGS = [
        ('a', 'add_task', 'add'),
        ('d', 'set_due', 'due date'),
        ('c', 'complete', 'complete'),
        ('p', 'priority', 'priority'),
        ('e', 'edit', 'edit'),
        ('left', 'focus_left'),
        ('right', 'focus_right')
    ]

    CSS = '''
        Screen {
            layout: horizontal;
        }

        #left, #right {
            height: 100%;
            border: solid #242F38;
        }

        #left {
            width: 25%;
        }

        #right {
            width: 75%;
        }

        ListView {
            background: #121212;
        }

        ListView :focus {
            background: black;
        }

        .complete {
            color: #01543c;
        }

        .warning {
            color: #D20000;
        }
    '''

    active_panel = 'right'
    highlighted_task = None
    highlighted_date = datetime.now().strftime('%Y-%m-%d')
    active_input = None

    # =========================
    #  Database interactions
    # ========================= 

    class Database():
        con = sqlite3.connect(f'{THIS_DIRECTORY}data.db')
        cursor = con.cursor()

        def add_task(self, description, due=None, priority=0) -> None:
            if due is None:
                due = datetime.now().strftime('%Y-%m-%d')
            self.cursor.execute(
                'INSERT INTO tasks (description, due, priority) VALUES (?, ?, ?)',
                (description, due, priority)
            )
            self.con.commit()

        def edit_description(self, task_id, new_description) -> None:
            self.cursor.execute(
                'UPDATE tasks SET description=? WHERE task_id=?',
                (new_description, task_id)
            )
            self.con.commit()

        def get_all_tasks(self, due=None) -> list:
            if due is None:
                due = datetime.now().strftime('%Y-%m-%d')
            self.cursor.execute(
                'SELECT task_id, description, due, priority, complete FROM tasks WHERE due=?',
                (due, )
            )
            rows = self.cursor.fetchall()
            tasks = []
            if rows is not None:
                for row in rows:
                    tasks.append({
                        'task_id':row[0],
                        'description':row[1],
                        'due':row[2],
                        'priority':row[3],
                        'complete':row[4] == 'TRUE'
                    })
            return tasks

        def get_dates(self) -> list:
            self.cursor.execute(
                '''
                SELECT
                    due,
                    SUM(CASE WHEN complete = 'FALSE' THEN 1 ELSE 0 END) AS incomplete_count,
                    SUM(CASE WHEN complete = 'TRUE' THEN 1 ELSE 0 END) AS complete_count,
                    SUM(CASE WHEN priority = 1 AND complete = 'FALSE' THEN 1 ELSE 0 END) AS priority_count
                FROM tasks
                GROUP BY due
                HAVING SUM(CASE WHEN complete = 'FALSE' THEN 1 ELSE 0 END) > 0
                ORDER BY due;
                '''
            )
            rows = self.cursor.fetchall()
            dates = []
            if rows is not None:
                for row in rows:
                    dates.append({
                        'date': row[0],
                        'incomplete_count': row[1],
                        'complete_count': row[2],
                        'priority_count': row[3],
                    })
            return dates

        def get_task(self, task_id) -> dict:
            self.cursor.execute(
                'SELECT task_id, description, due, priority, complete FROM tasks WHERE task_id=?',
                (task_id, )
            )
            row = self.cursor.fetchone()
            if row is not None:
                return {
                    'task_id':row[0],
                    'description':row[1],
                    'due':row[2],
                    'priority':row[3],
                    'complete':row[4] == 'TRUE'
                }
            else:
                return {}

        def set_due(self, task_id, due_date) -> None:
            self.cursor.execute(
                'UPDATE tasks SET due=? WHERE task_id=?',
                (due_date, task_id)
            )
            self.con.commit()

        def toggle_complete(self, task_id) -> None:
            self.cursor.execute(
                'SELECT complete FROM tasks WHERE task_id=?',
                (task_id,)
            )
            rows = self.cursor.fetchone()
            if rows:
                if rows[0] == 'TRUE':
                    new_status = 'FALSE'
                else:
                    new_status = 'TRUE'
                self.cursor.execute(
                    'UPDATE tasks SET complete=? WHERE task_id=?',
                    (new_status, task_id)
                )
                self.con.commit()

        def toggle_priority(self, task_id) -> None:
            self.cursor.execute(
                'SELECT priority FROM tasks WHERE task_id=?',
                (task_id,)
            )
            rows = self.cursor.fetchone()
            if rows:
                if rows[0] == 0:
                    new_status = 1
                else:
                    new_status = 0
                self.cursor.execute(
                    'UPDATE tasks SET priority=? WHERE task_id=?',
                    (new_status, task_id)
                )
                self.con.commit()

    db = Database()
    
    # =========================
    #  Custom widgets
    # ========================= 

    class TaskItem(ListItem):
        '''Custom widget for tasks based on ListItem'''
        def __init__(self, task_id: int, description: str, complete: bool, priority: int) -> None:
            super().__init__()
            self.description = description
            self.task_id = task_id
            self.complete = complete
            self.priority = priority

        def compose( self ) -> ComposeResult:
            if self.complete:
                yield Label(
                    f' 🗹 {self.description} ',
                    classes='complete'
                )
            elif self.priority != 0:
                yield Label(
                    f' ☐ {self.description} ',
                    classes='warning'
                )
            else:
                yield Label(
                    f' ☐ {self.description} ',
                )

    class DateItem(ListItem):
        '''Custom widget for dates based on ListItem'''
        def __init__(self, due: str, priority_count: int, incomplete_count: int, complete_count: int) -> None:
            super().__init__()
            self.due = due
            self.priority_count = priority_count
            self.incomplete_count = incomplete_count
            self.complete_count = complete_count

        def compose( self ) -> ComposeResult:
            if self.due == datetime.now().strftime('%Y-%m-%d'):
                due_text = 'Today'
            else:
                due_text = self.due

            if self.due < datetime.now().strftime('%Y-%m-%d'):
                yield Label(
                    f' {due_text.ljust(10)} [{str(self.complete_count).rjust(1)}/{str(self.complete_count + self.incomplete_count).rjust(1)}] '              
                )
            else:
                yield Label(
                    f' {due_text.ljust(10)} [{str(self.complete_count).rjust(1)}/{str(self.complete_count + self.incomplete_count).rjust(1)}] '
                )

    # =========================
    #  Actions
    # ========================= 

    def action_add_task(self) -> None:
        '''Add a new task to the currently selected date'''
        self.active_input = 'new_task'
        input_widget = Input(
            placeholder='new task description'
        )
        self.query_one('#right').mount(input_widget)
        input_widget.focus()

    def action_complete(self) -> None:
        '''Toggle completion state of highlighted task'''
        if self.active_panel == 'right':
            self.db.toggle_complete(self.highlighted_task)
            self.show_tasks()
            self.show_dates()

    def action_edit(self) -> None:
        '''Edit highlighted task's description'''
        if self.active_panel == 'right':
            self.active_input = 'edit_task'
            input_widget = Input(
                value=self.db.get_task(self.highlighted_task).get('description','')
            )
            self.query_one('#right').mount(input_widget)
            input_widget.focus()

    def action_focus_left(self) -> None:
        '''Move focus to date panel'''
        self.active_panel = 'left'
        self.query_one('#date_list').focus()


    def action_focus_right(self) -> None:
        '''Move focus to task panel'''
        self.active_panel = 'right'
        self.query_one('#task_list').focus()

    def action_priority(self) -> None:
        '''toggle priority state of highlighted task'''
        if self.active_panel == 'right':
            self.db.toggle_priority(self.highlighted_task)
            self.show_tasks()
            self.show_dates()

    def action_set_due(self) -> None:
        '''Set due date of highlighted task'''
        if self.active_panel == 'right':
            self.active_input = 'set_due'
            input_widget = Input(
                value=self.db.get_task(self.highlighted_task).get('due','')
            )
            self.query_one('#right').mount(input_widget)
            input_widget.focus()

    # =========================
    #  Screen updates
    # ========================= 

    def compose(self) -> ComposeResult:
        '''Create child widgets for the app.'''   
        yield Header()

        date_list = ListView(id='date_list')
        yield Container(
            date_list,
            id='left'
            )

        task_list = ListView(id='task_list')
        yield Container(
            task_list,
            id='right'
        )

        task_list.focus()

        yield Footer()
    
    def show_dates(self) -> None:
        '''Read tasks from db & list dates that have at least one task'''
        dates = [self.DateItem(d['date'], d['priority_count'], d['incomplete_count'], d['complete_count'],) for d in self.db.get_dates()]
        date_list = self.query_one('#date_list')
        for child in date_list.children:
            child.remove()
        date_list.extend(dates)

    def show_tasks(self) -> None:
        '''Read tasks from db & inset into UI list'''
        tasks = [self.TaskItem(t['task_id'], t['description'], t['complete'], t['priority']) for t in self.db.get_all_tasks(self.highlighted_date)]
        task_list = self.query_one('#task_list')
        for child in task_list.children:
            child.remove()
        task_list.extend(tasks)

    def on_mount(self):
        '''Happens after all widgets have been drawn on-screen'''
        self.show_dates()
        self.show_tasks()

    # =========================
    #  Stuff triggered by user
    # ========================= 

    def on_input_submitted(self, event: Input.Submitted) -> None:
        '''Triggered after Enter pressed in Input widget'''
        value = event.value
        if value != '':
            if self.active_input == 'new_task':
                self.db.add_task(value)
            if self.active_input == 'edit_task':
                self.db.edit_description(self.highlighted_task, value)
            if self.active_input == 'set_due':
                self.db.set_due(self.highlighted_task, value)

        event.input.remove()
        self.show_tasks()
        self.show_dates()

    def on_list_view_highlighted(self, event: ListView.Selected):
        '''Navigate between tasks or dates'''
        if self.active_panel == 'right':
            self.highlighted_task = event.item.task_id
        elif self.active_panel == 'left':
            self.highlighted_date = event.item.due
            self.show_tasks()
        
    

if __name__ == '__main__':
        app = ToDo()
        app.run()
