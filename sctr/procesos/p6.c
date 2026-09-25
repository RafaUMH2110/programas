/* Ejemplo de acceso a memoria dinamica en varios procesos 
	Espacio de memoria separado -> las variables son diferentes

	Compilar con:		gcc p6.c -o p6
	
	Ejecutar con:		./p6
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/wait.h>

int *global;

int main(void)
{
	pid_t pid;
	int i = 0;
	global = (int *) malloc (sizeof(global));
	*global = 0;
	
	pid=fork();
	switch (pid)
	{
		case -1: 
				 	perror("Error al crear el hijo");
					 exit(1);
		
		case 0:
					printf("Soy el hijo e incremento global hasta 10\n");
					for (i=1; i<10;i++)
					{	
						*global=i;
						printf("Soy el hijo y global vale %d \n",*global);
						sleep(1);
					}
					break;
				
		default:
					printf("Soy el Padre y leo el valor actual de global \n");
					for (i=1;i<10;i++)
					{
						printf("Soy el padre, global vale %d\n", *global);
						sleep(1);
					}
					printf("Soy el padre, espero al hijo y termino\n");
					wait(0);
	}
	exit(0);
}
					
					
	
