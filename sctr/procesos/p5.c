/* Ejemplo de acceso al mismo fichero desde varios procesos

	Compilar con:		gcc p5.c -o p5
	
	Ejecutar con:		./p5
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>

FILE *fd;

int  main(void)
{
	pid_t pid;
	int i = 0;
	int dato=0;

	
	fd = fopen ("fichero", "w+");
	fprintf(fd, "%d ", dato);
	
	pid=fork();
	switch (pid)
	{
		case -1: 	perror("Error al crear el hijo");
				 exit(1);
				
		
		case 0: printf("Soy el hijo y leo el fichero\n");
				for (i=0;i<10;i++)
				{
						sleep(1);
						fseek (fd, 0L,SEEK_SET);
						fscanf(fd, "%d", &dato);
						printf("Soy el hijo y dato vale %d \n",dato);
				}
				break;
			
		default:	printf("Soy el padre y escribo en el fichero\n");
					for (i=0;i<10;i++)
					{
						fseek (fd, 0L,SEEK_SET);
						fprintf(fd, "%d", i);
						sleep(1);
					}
					printf("Soy el padre, espero al hijo y termino\n");
					wait(0);
	}
	exit(0);
}
					
					
	
