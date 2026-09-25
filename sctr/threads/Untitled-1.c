#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>    
#include <unistd.h>

void* thread_function(void* arg) {
    int thread_num = *((int*)arg);
    printf("Thread %d is running\n", thread_num);
    sleep(1); // Simulate some work
    printf("Thread %d is exiting\n", thread_num);
    return NULL;
}
int main() {
    #define NUM_THREADS 5
    pthread_t threads[NUM_THREADS];
    int thread_args[NUM_THREADS];

    for (int i = 0; i < NUM_THREADS; i++) {
        thread_args[i] = i + 1; // Thread numbers start from 1
        if (pthread_create(&threads[i], NULL, thread_function, &thread_args[i]) != 0) {
            perror("Failed to create thread");
            return EXIT_FAILURE;
        }
    }

    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("All threads have finished execution\n");
    return EXIT_SUCCESS;
}
