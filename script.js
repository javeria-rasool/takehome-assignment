const todoList = document.getElementById('todo-list');
const newTodoInput = document.getElementById('new-todo');
const addTodoButton = document.getElementById('add-todo');
const todoCountElement = document.getElementById('todo-count');
let todos = JSON.parse(localStorage.getItem('todos')) || [];

function renderTodos() {
	todoList.innerHTML = '';
	todos.forEach((todo, index) => {
		const todoItem = document.createElement('li');
		todoItem.classList.add('todo-item', todo.completed ? 'completed' : '');
		todoItem.innerHTML = `
			<span>${todo.text}</span>
			<button class="delete" onclick="deleteTodo(${index})">×</button>
		`; todoItem.querySelector('.delete').addEventListener('click', () => deleteTodo(index));
		todoList.appendChild(todoItem);
	});
	todoCountElement.textContent = `Remaining: ${todos.filter(todo => !todo.completed).length}`;
}

function addTodo() {
	const newTodoText = newTodoInput.value.trim();
	if (newTodoText) {
		todos.push({ text: newTodoText, completed: false });
		localStorage.setItem('todos', JSON.stringify(todos));
		renderTodos();
		newTodoInput.value = '';
	}
}

function deleteTodo(index) {
	todos.splice(index, 1);
	localStorage.setItem('todos', JSON.stringify(todos));
	renderTodos();
}

function toggleTodo(index) {
	todos[index].completed = !todos[index].completed;
	localStorage.setItem('todos', JSON.stringify(todos));
	renderTodos();
}

addTodoButton.addEventListener('click', addTodo);
newTodoInput.addEventListener('keypress', event => {
	if (event.key === 'Enter') {
		addTodo();
	}
});
renderTodos();