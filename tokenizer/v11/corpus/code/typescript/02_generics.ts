function identity<T>(value: T): T {
    return value;
}

function map<T, U>(items: T[], fn: (item: T) => U): U[] {
    const out: U[] = [];
    for (const item of items) {
        out.push(fn(item));
    }
    return out;
}

async function processQueue<T>(
    items: T[],
    handler: (item: T) => Promise<void>,
): Promise<void> {
    for (const item of items) {
        try {
            await handler(item);
        } catch (error) {
            console.error(`failed: ${error}`);
        }
    }
}

type ReadOnly<T> = {
    readonly [K in keyof T]: T[K];
};

type Partial<T> = {
    [K in keyof T]?: T[K];
};
