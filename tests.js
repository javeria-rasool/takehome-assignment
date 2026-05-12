import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync('index.html', 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously' });
const document = dom.window.document;
const window = dom.window;

describe('Todo App', () => {
  it('adds a new todo item', () => {
    const input = document.querySelector('input');
    const button = document.querySelector('button');
    input.value = 'New todo item';
    button.click();
    const todoItems = document.querySelectorAll('li');
    expect(todoItems.length).toBe(1);
  });

  it('marks a todo as complete', () => {
    const input = document.querySelector('input');
    const button = document.querySelector('button');
    input.value = 'New todo item';
    button.click();
    const todoItem = document.querySelector('li');
    const checkbox = todoItem.querySelector('input');
    checkbox.click();
    expect(todoItem.classList.contains('completed')).toBe(true);
  });

  it('deletes a todo item', () => {
    const input = document.querySelector('input');
    const button = document.querySelector('button');
    input.value = 'New todo item';
    button.click();
    const todoItem = document.querySelector('li');
    const deleteButton = todoItem.querySelector('button');
    deleteButton.click();
    const todoItems = document.querySelectorAll('li');
    expect(todoItems.length).toBe(0);
  });

  it('shows a count of remaining incomplete items', () => {
    const input = document.querySelector('input');
    const button = document.querySelector('button');
    input.value = 'New todo item';
    button.click();
    const input2 = document.querySelector('input');
    const button2 = document.querySelector('button');
    input2.value = 'New todo item 2';
    button2.click();
    const todoItems = document.querySelectorAll('li');
    const count = document.querySelector('.count');
    expect(count.textContent).toBe('2 items left');
  });

  it('persists todos in localStorage', () => {
    const input = document.querySelector('input');
    const button = document.querySelector('button');
    input.value = 'New todo item';
    button.click();
    window.location.reload();
    const todoItems = document.querySelectorAll('li');
    expect(todoItems.length).toBe(1);
  });
});