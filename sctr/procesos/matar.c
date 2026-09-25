/* 
	Ejemplo de uso de la función kill()

	Compilar con: 		gcc matar.c -o matar 
	
	Ejecutar con:		./matar
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/signal.h>

int main(void)
{
   	pid_t childpid;
   	int res;
   	
  	childpid = fork();

	if (childpid == -1)
	{
		perror("fork no pudo crear el hijo");
		exit(1);
	}
  	else  if (childpid == 0)
  	{
	  printf ("Soy el hijo (PID %d) y me voy a colgar\n", getpid());
	  while(1) {}
  	}
  	else 
  	{
	  printf("Soy el padre y voy a terminar a mi hijo\n");
	  sleep(2);  /* espero 2 segundos -> Estado Suspendido */
	  if ((res = kill(childpid, SIGKILL))==-1) 
		perror("no he podido terminar al hijo");
	  else
		printf("Mi hijo con pid %d, ha muerto\n",childpid);
  	}
  	exit(0);
}
