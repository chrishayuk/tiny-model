package main

import (
    "fmt"
    "sync"
)

type Result struct {
    Index int
    Value int
}

func worker(id int, jobs <-chan int, results chan<- Result, wg *sync.WaitGroup) {
    defer wg.Done()
    for job := range jobs {
        results <- Result{Index: id, Value: job * job}
    }
}

func main() {
    jobs := make(chan int, 100)
    results := make(chan Result, 100)
    var wg sync.WaitGroup

    for w := 1; w <= 3; w++ {
        wg.Add(1)
        go worker(w, jobs, results, &wg)
    }

    for j := 1; j <= 10; j++ {
        jobs <- j
    }
    close(jobs)

    go func() {
        wg.Wait()
        close(results)
    }()

    for r := range results {
        fmt.Printf("worker %d: %d\n", r.Index, r.Value)
    }
}
