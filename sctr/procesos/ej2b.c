/* Ejercicio 2b: lanzar un comando en backgroud con uno  o ningun parametro 

	Compilar con:		gcc ej2b.c -o ej2b 
	
	Ejecutar con:		./ej2b
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
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
	  if(argc>1 && argc<4)
	  {		
			printf("Soy el hijo y voy a ejecutar el comando %s",argv[1]);
			if(argc==3) printf(" %s\n",argv[2]);
			else printf("\n");

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

