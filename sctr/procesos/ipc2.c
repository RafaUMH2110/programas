/* ejemplo de uso de semaforos no nombrados con memoria compartida

	Compilar con:		gcc ipc2.c -o ipc2 -lposix4
	Compilar linux: 	gcc ipc2.c -o ipc2 -lrt
	
	Ejecutar con:		./ipc2
*/


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sched.h>  /* Para la funcion sched_yield() */

#include <sys/ipc.h>
#include <sys/shm.h>
#include <semaphore.h>

#define NUM_PROCESOS	10
#define BUFFER_SIZE	500
#define SHM_SIZE sizeof(sem_t)  /* memoria compartida  para el sem‡foro */

char buffer[BUFFER_SIZE];

int main (int argc, char *argv[])
{
	char *c;
	int i, n=NUM_PROCESOS;
	pid_t hijo;
	sem_t *semaforo;
	int shmid;		// manejador de memoria compartida
    key_t key;


	printf("Creando Region de memoria compartida .....\n");
    /* Crea la clave: */
   if ((key = ftok("ipc2", 0)) == -1) {
            perror("Error creando clave con ftok");  
			exit(1);
   }
    /* Crear/conectar el segmento de memoria: */
    if ((shmid = shmget(key, sizeof(sem_t), IPC_CREAT | 0644)) == -1) {
            perror("Error creando segmento memoria con shmget");
            exit(1);
    }

    /* Enlaza (attach) el segmento de memoria para obtener un puntero al mismo: */
    semaforo = (sem_t *) shmat(shmid, (void *)0, 0);
    if (semaforo == (sem_t *)(-1)) {
            perror("Error obteniendo el puntero con shmat");
            exit(1);
    }

	
	/* Crea el semaforo no nombrado */
	if (sem_init(semaforo, 1, 1) == -1)
	{
		perror("No se puede crear el semaforo");
		exit(1);
	}
	/* Crea los procesos */
	for (i = 1; i<n; ++i)
	{
		hijo = fork();
		if (hijo==-1)
		{
			perror("No se puede crear el proceso");	exit(-1);
		}
		else if (hijo==0)	// si es un hijo terminar el for (solo el padre crea los hijos)
			break;
	}
	/* i actua como identificador del proceso */
	/* en el padre i==n */

	sprintf(buffer, "i:%d  proceso ID:%d  padre ID:%d\n",i, 
			getpid(), getppid());
	c = buffer;

	/********* Seccion de entrada ****/
	if (sem_wait(semaforo) == -1)
	{
		perror("Semaforo no valido");
		exit(1);
	}
	/**** Principio de la seccion critica *******/
	while (*c != '\0')
	{
		fputc(*c, stderr); fflush(stderr);
		c++;
		sched_yield();	/* liberamos la CPU */

	}
	/********** Fin de la seccion critica *******/
	
	/*********** Seccion de salida ************/
	if (sem_post(semaforo) == -1)
	{
		perror("Semaforo no valido");
		exit(1);
	}
	/********* Seccion Restante ************/

	// El Padre espera que terminen los hijos
	if(i==n)
	{
		printf("\nSoy el Padre [PID:%d] y voy a esperar que terminen todos los hijos\n", getpid());
		for(i=1;i<n;i++)
			wait(0);
		
		printf("Soy el padre destruyo los semaforos/memoria compartida y termino.....\n");

		/* destruyo semaforos (solo el padre) */
		sem_destroy(semaforo);
			
		/* elimino segmento de memoria compartida */
		if (shmctl(shmid, IPC_RMID , NULL) == -1) {
				perror("Error eliminando segmento de memoria con shmctl");
				exit(1);
		}

	}
	exit(0);
}
