import { useState, useEffect, useCallback } from "react";

interface Props {
    userId: string;
    onSave?: (user: User) => void;
}

export function UserProfile({ userId, onSave }: Props) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            try {
                const response = await fetch(`/api/users/${userId}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const data: User = await response.json();
                setUser(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "unknown error");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [userId]);

    const handleSave = useCallback(async () => {
        if (!user) return;
        await fetch(`/api/users/${userId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(user),
        });
        onSave?.(user);
    }, [user, userId, onSave]);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;
    if (!user) return null;

    return (
        <div className="user-profile">
            <h1>{user.name}</h1>
            <p>Email: {user.email}</p>
            <button onClick={handleSave}>Save</button>
        </div>
    );
}
