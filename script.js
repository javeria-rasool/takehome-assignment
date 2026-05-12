let todos = JSON.parse(localStorage.getItem('todos')) || [];
const newTodoInput = document.getElementById('new-todo');
const addTodoButton = document.getElementById('add-todo');
const todoList = document.getElementById('todo-list');
const remainingCount = document.getElementById('remaining-count');

addTodoButton.addEventListener('click', () => {
    const newTodo = newTodoInput.value.trim();
    if (newTodo) {
        todos.push({ text: newTodo, completed: false });
        localStorage.setItem('todos', JSON.stringify(todos));
        renderTodos();
        newTodoInput.value = '';
    }
});

function renderTodos() {
    todoList.innerHTML = '';
    todos.forEach((todo, index) => {
        const todoItem = document.createElement('li');
        todoItem.classList.add('todo-item');
        if (todo.completed) {
            todoItem.classList.add('completed');
        }
        todoItem.innerHTML = `
            <span>${todo.text}</span>
            <button class="delete" onclick="deleteTodo(${index})">Delete</button>
        `;
        todoList.appendChild(todoItem);
    });
    remainingCount.textContent = todos.filter(todo => !todo.completed).length;
}

function deleteTodo(index) {
    todos.splice(index, 1);
    localStorage.setItem('todos', JSON.stringify(todos));
    renderTodos();
}

function toggleCompleted(index) {
    todos[index].completed = !todos[index].completed;
    localStorage.setItem('todos', JSON.stringify(todos));
    renderTodos();
}

renderTodos();