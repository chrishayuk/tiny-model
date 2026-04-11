package main

import (
    "fmt"
    "math"
    "strings"
)

type Point struct {
    X, Y float64
}

func (p Point) Distance(q Point) float64 {
    return math.Hypot(p.X-q.X, p.Y-q.Y)
}

func fibonacci(n int) int {
    if n <= 1 {
        return n
    }
    return fibonacci(n-1) + fibonacci(n-2)
}

func main() {
    p := Point{X: 1.0, Y: 2.0}
    q := Point{X: 4.0, Y: 6.0}
    fmt.Printf("distance: %.2f\n", p.Distance(q))

    words := strings.Split("the quick brown fox", " ")
    for i, word := range words {
        fmt.Printf("%d: %s\n", i, word)
    }

    sum := 0
    for i := 0; i < 10; i++ {
        sum += i * i
    }
    fmt.Println("sum of squares:", sum)
}
