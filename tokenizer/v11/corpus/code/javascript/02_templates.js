const greet = (name) => `Hello, ${name}!`;
const url = `https://api.example.com/users/${userId}`;
const query = `SELECT * FROM users WHERE id = ${id}`;

const response = await fetch(`/api/users/${id}`);
const data = await response.json();
console.log(`got ${data.length} results`);

try {
    const result = await processItem(item);
    console.log(`processed: ${result}`);
} catch (error) {
    console.error(`failed: ${error.message}`);
}

const items = users.map(user => user.name).filter(name => name.length > 0);
const total = orders.reduce((sum, order) => sum + order.price, 0);
const grouped = users.groupBy(user => user.department);

const { name, email, age = 18 } = user;
const [first, second, ...rest] = items;
const copy = { ...obj, updatedAt: Date.now() };

class UserService {
    constructor(db) {
        this.db = db;
    }

    async findById(id) {
        return await this.db.users.findOne({ id });
    }

    async create(data) {
        return await this.db.users.insertOne(data);
    }
}
