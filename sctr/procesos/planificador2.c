/* 
	Ejemplo de uso de cambio de politica de planificacion de procesos

	Compilar con: 		gcc planificador2.c -o planificador2 -lposix4
	Compilar linux: 	gcc planificador2.c -o planificador2 -lrt
	
	Ejecutar con:		./planificador2
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
  struct sched_param scheduling_parameters;
  int res;
  struct timespec quantum;

  
  scheduling_parameters.sched_priority = 17;
  res = sched_setscheduler(getpid(), SCHED_RR, &scheduling_parameters);
  
  if(sched_rr_get_interval(getpid(), &quantum)==0)
	printf("Quantum: %f ms\n", (float)quantum.tv_nsec/1000000L);

  exit(0);
}


