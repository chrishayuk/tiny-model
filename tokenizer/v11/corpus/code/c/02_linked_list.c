#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int value;
    struct Node *next;
} Node;

Node *create_node(int value) {
    Node *node = (Node *)malloc(sizeof(Node));
    if (node == NULL) {
        fprintf(stderr, "out of memory\n");
        exit(1);
    }
    node->value = value;
    node->next = NULL;
    return node;
}

void append(Node **head, int value) {
    Node *node = create_node(value);
    if (*head == NULL) {
        *head = node;
        return;
    }
    Node *cur = *head;
    while (cur->next != NULL) cur = cur->next;
    cur->next = node;
}

void free_list(Node *head) {
    while (head != NULL) {
        Node *next = head->next;
        free(head);
        head = next;
    }
}

typedef unsigned int uint32_t;

uint32_t hash(const char *key) {
    uint32_t h = 5381;
    for (size_t i = 0; key[i] != '\0'; i++) {
        h = ((h << 5) + h) + (unsigned char)key[i];
    }
    return h;
}
