/* Ejemplo: calculo de potencias d enúmeros pares e impares usando tres procesos

	Compilar con:		gcc ej3.c -o ej3 
	
	Ejecutar con:		./ej3
*/

#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>

FILE *fd1;
FILE *fd2;

int main(void)
{
  pid_t childpid1, childpid2, childdead;
  int i;
  int dato;
  
  fd1 = fopen ("impares.dat", "w+");
	
  childpid1 = fork();
  
  switch (childpid1)
  {
   case -1: perror("No se ha podido crear el hijo 1\n");
   			break;
   
   case 0: printf("Soy el hijo1, mi PID es %d y voy a calcular los numeros impares\n",getpid());

			fd1 = fopen ("impares.dat", "w+");

   			for(i=1;i<=20;i+=2){
	   		   //	fseek (fd1, 0L,SEEK_SET);
				fprintf(fd1, "%d\n", i*i);
   			}
   			break;
   			
   
   default: printf("Soy el padre, mi PID es %d y voy a crear al segundo hijo\n",getpid());
   			childpid2 = fork();
   			if (childpid2==-1)
   			{
	   			perror ("No se ha podido crear el hijo 2\n");
	   			break;
   			}
   			else if(childpid2==0)
   			{
			    fd2 = fopen ("pares.dat", "w+" );
	   			printf("Soy el hijo 2, mi PID es %d y voy a calcular los numero pares\n", getpid());
	   			for(i=0;i<=20;i+=2){
	   		   	//fseek (fd2, 0L,SEEK_SET);
				fprintf(fd2, "%d\n", i*i);
   			}
	   			break;
   			}
   			else 
   			{
	   			printf("Soy el padre y voy a esperar a los dos hijos\n");
	   			wait(0);
	   			wait(0);
	   			fseek (fd1, 0L,SEEK_SET);
	   			fseek (fd2, 0L,SEEK_SET);
	   			for (i=0;i<=10;i++)
				{
						//sleep(1);
						//fseek (fd1, 0L,SEEK_SET);
						fscanf(fd2, "%d\n", &dato);
						printf("Soy el padre y las potencias son: %d \n",dato);
						//fseek (fd2, 0L,SEEK_SET);
						fscanf(fd1, "%d\n", &dato);
						printf("Soy el padre y las potencias son: %d \n",dato);
				}
	   			
   			}
  }

  
  exit(0);
}