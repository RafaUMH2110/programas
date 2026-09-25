
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>

#define BLKSIZE	100 		/*tama�o del buffer*/
                                 
int main (void)
{
  int fd, bytes_escritos;			/*descriptor de fichero*/
  char buffer[BLKSIZE];	
  mode_t modo = S_IRWXU; /* modo de r, w y x para el propietario*/

  strcpy(buffer, "Esto es un ejemplo\n");
  if ((fd = open ("ejemplo", O_RDWR | O_CREAT, modo))== -1)
	/*abre el fichero ejemplo en modo lectura/escritura o lo
	crea si no existe */
	perror ("Error al abrir o crear el fichero");
	/*muestra un mensaje de error si no puede abrir/crear el fichero*/
  else
	bytes_escritos = write(fd, buffer, strlen(buffer));
	/* escribe buffer de tama�o sizeof(buffer) en fd */
  exit(0);
}
