/* Ejemplo Ejemplo de uso de la funcion  execvp()
	Cambia la imagen en memoria de un proceso 

	Compilar con:		gcc p4.c -o p4
	
	Ejecutar con:		./p4
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/wait.h>

int main (int argc, char *argv[])
{
  pid_t childpid;
  
  childpid = fork();

  if (childpid == -1)
  {
	perror("Error al crear el hijo");
	exit(1);
  }
  else if (childpid ==0)
  {
	  if(argc>1)
	  {
			printf("Soy el hijo y voy a ejecutar el comando %s\n",argv[1]);
			if(execvp(argv[1], &argv[1])<0) 
			{
				perror("Error al ejecutar el comando");
				exit (1);
			}
	  } else 
		  printf("Soy el hijo y no has escrito ningun comando\n");
  }
  else
  {
	printf("Soy el padre, espero al hijo y termino\n");
	wait(0);
  }  
  
  exit(0);
}

