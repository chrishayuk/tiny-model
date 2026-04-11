public interface Shape {
    double area();
    double perimeter();
    String name();
}

public class Circle implements Shape {
    private final double radius;

    public Circle(double radius) {
        this.radius = radius;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }

    @Override
    public double perimeter() {
        return 2 * Math.PI * radius;
    }

    @Override
    public String name() {
        return "circle";
    }
}

public abstract class Animal {
    protected final String name;
    protected final int age;

    protected Animal(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public abstract String speak();
}
