/* ejemplo de uso de memoria compartida (seccion critica) 
	mediante semaforos

	Compilar con:		gcc ipc1.c -o ipc1 -lposix4
	Compilar linux: 	gcc ipc1.c -o ipc1 -lrt
	
	Ejecutar con:		./ipc1
*/

#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>

#include <sys/ipc.h>
#include <sys/shm.h>
#include <semaphore.h>

#define SHM_SIZE 1024  /* 1K segmento de memoria compartida  */

sem_t *sem_1;	// puntero para el identificador de los semáforos
int shmid;		// manejador de memoria compartida

int main(void)
{
	int i,j;
    key_t key;
	pid_t hijo;
    int *data;
	
	printf("Creando semaforos .....\n");
	/* comprueba si ya existe el semaforo, sino lo crea desbloqueado (1)*/
	if((sem_1=sem_open("/sem_ipc1", O_CREAT, 0644, 1))==(sem_t *)-1)
		perror("Error creando semaforo 1");

	printf("Creando Region de memoria compartida .....\n");

    /* Crea la clave: */
   if ((key = ftok("ipc1", 0)) == -1) {
            perror("Error creando clave con ftok");  
			exit(1);
   }
    /* Crear/conectar el segmento de memoria: */
    if ((shmid = shmget(key, SHM_SIZE, IPC_CREAT | 0644)) == -1) {
            perror("Error creando segmento memoria con shmget");
            exit(1);
    }

    /* Enlaza (attach) el segmento de memoria para obtener un puntero al mismo: */
    data = (int *) shmat(shmid, (void *)0, 0);
    if (data == (int *)(-1)) {
            perror("Error obteniendo el puntero con shmat");
            exit(1);
    }
	printf("Creando proceso hijo .....\n");

	/* creamos el hijo */
	hijo=fork() ;

	switch(hijo)
	{
		case -1:
			
			printf("error creando proceso hijo\n");
			exit(-1);
			
		case 0:	/* estamos en el hijo, escribir valores en segmento de memoria */
			printf("Soy el hijo con PID (escribo en el buffer):%d\n", getpid());
			
			for (i=0;i<10;i++)
			{
				sem_wait(sem_1);	/* Seccion de entrada */
				/* Seccion Critica */
					data[i]=i;
				/* Fin de seccion Critica */
				sem_post(sem_1); /* Seccion de salida  */
				sleep(2);
			}

			/* libero semáforos */
			sem_close(sem_1);

	        /* Deconecta (detach) el segmento de memoria compartida: */
			if (shmdt((char *)data) == -1) {
				perror("Error desconectado segmento de memoria con shmdt");
				exit(1);
			}

			printf("Soy el hijo y termino.....\n");
		break;

		default: /*estamos en el padre, leer valores del segmento compartido */
			printf("Soy el padre con PID (leo del buffer):%d\n", getpid());

			/* muestra el contenido del buffer */
			for (j=0;j<20;j++)
			{
		
				sem_wait(sem_1);	/* Seccion de entrada */
				/* Seccion Critica: muestra los 10 valores */
				for (i=0;i<10;i++)
						printf("%3d ",data[i]);
				printf("\n");
				/* Fin de seccion Critica */
				sem_post(sem_1); /* Seccion de salida  */
				sleep(1);
			}

			/* libero semáforos */
			sem_close(sem_1);

	        /* Desconecta (detach) el segmento de memoria compartida: */
			if (shmdt((char *)data) == -1) {
				perror("Error desconectado segmento de memoria con shmdt");
				exit(1);
			}

			printf("Soy el padre espero que termine el hijo .....\n");
			wait(0); /* Esperar que acabe el hijo */

			printf("Soy el padre destruyo los semaforos/memoria compartida y termino.....\n");

			/* destruyo semaforos (solo el padre) */
			sem_unlink("/sem_1");
			
			/* elimino segmento de memoria compartida */
			if (shmctl(shmid, IPC_RMID , NULL) == -1) {
				perror("Error eliminando segmento de memoria con shmctl");
				exit(1);
			}
	
	}
	exit(0);
}
