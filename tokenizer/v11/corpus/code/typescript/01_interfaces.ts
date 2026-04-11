interface User {
    id: number;
    name: string;
    email: string;
    age?: number;
}

interface Comparable<T> {
    compareTo(other: T): number;
}

type Result<T> =
    | { ok: true; value: T }
    | { ok: false; error: string };

enum Status {
    Pending = "pending",
    Active = "active",
    Archived = "archived",
}

class UserRepository {
    private users: Map<number, User> = new Map();

    public add(user: User): void {
        this.users.set(user.id, user);
    }

    public get(id: number): User | undefined {
        return this.users.get(id);
    }

    public all(): readonly User[] {
        return Array.from(this.users.values());
    }
}

export default UserRepository;
