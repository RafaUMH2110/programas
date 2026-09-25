/* Ejemplo de procesos zoombies 

	Compilar con:		gcc ej2.c -o ej2 
	
	Ejecutar con:		./ej2
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/wait.h>

int main(void)
{
   pid_t childpid, childdead;
   int i;

  childpid = fork();

  if (childpid == -1)
  {
		perror("fork no pudo crear el hijo");
		exit(1);
  }
  else  if (childpid == 0)
  {
       printf ("Soy el hijo (PID %d) y mi padre es (PID %d), voy a esperar \n", getpid(), getppid());
       sleep(6);
       printf ("Soy el hijo (PID %d) y mi padre es (PID %d)\n", getpid(), getppid());
  }
  else 
  {
	  printf("Soy el padre (PID %d) y voy terminar sin esperar a mi hijo (PID %d)\n", getpid(), childpid);
	 
  }
  
  exit(0);
}
