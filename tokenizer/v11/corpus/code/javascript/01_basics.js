function add(a, b) {
    return a + b;
}

const numbers = [1, 2, 3, 4, 5];
const doubled = numbers.map(x => x * 2);
const evens = numbers.filter(x => x % 2 === 0);
const total = numbers.reduce((acc, x) => acc + x, 0);

class Animal {
    constructor(name, sound) {
        this.name = name;
        this.sound = sound;
    }

    speak() {
        return `${this.name} says ${this.sound}`;
    }
}

const dog = new Animal("rex", "woof");
console.log(dog.speak());

const cache = new Map();
const seen = new Set();

async function fetchUser(id) {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}
