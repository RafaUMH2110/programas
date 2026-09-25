/* 
	Ejemplo de uso de cambio de politica de planificacion de procesos

	Compilar con: 		gcc planificador.c -o planificador -lposix4
	Compilar linux: 	gcc planificador.c -o planificador -lrt
	
	Ejecutar con:		./planificador
*/


#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <errno.h>
#include <sys/wait.h>

#include <sched.h>

int main (void)
{
  pid_t pid;
  struct sched_param scheduling_parameters;
  int i,res;
 
  
  scheduling_parameters.sched_priority = 17;
  res = sched_setscheduler(getpid(), SCHED_FIFO, &scheduling_parameters);
  
  
  pid = fork();
  switch (pid)
  {
	case -1: 
		perror ("No se ha podido crear el hijo");
		break;
	case 0:	
		printf("Soy el hijo, mi PID es %d y mi PPID es %d\n",
				getpid(), getppid());
		sleep(1); 
		for(i=0;i<10;i+=2)
		{ 
			printf("%ld\n",i); fflush(stdout);
			sleep(1); 
		}
		break;

	default:	
		printf ("Soy el padre, mi PID es %d y el PID de mi hijo es %d\n", 
							getpid(), pid);
  		sleep(1); 
		for(i=1;i<10;i+=2)
		{ 
			printf("%ld\n",i); fflush(stdout);
			sleep(1); 
		}
		// Espera que termine el hijo
		wait(0);
  }
  exit(0);
}


