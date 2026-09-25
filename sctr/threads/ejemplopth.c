#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <unistd.h>

void *thread_function(void *arg) {
    int id = *(int *)arg;
    printf("Thread %d running\n", id);
    sleep(1);
    printf("Thread %d done\n", id);
    return NULL;
}

int main() {
    pthread_t threads[2];
    int ids[2] = {1, 2};
    pthread_attr_t attr;
    struct sched_param param;

    pthread_attr_init(&attr);
    pthread_attr_setschedpolicy(&attr, SCHED_RR);
    param.sched_priority = 50;
    pthread_attr_setschedparam(&attr, &param);

    for (int i = 0; i < 2; i++) {
        pthread_create(&threads[i], &attr, thread_function, &ids[i]);
    }

    for (int i = 0; i < 2; i++) {
        pthread_join(threads[i], NULL);
    }

    pthread_attr_destroy(&attr);
    return 0;
}