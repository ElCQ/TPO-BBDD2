# TPO-BBDD2

## Instructivo de activacion

### Pre requisitos
Es nesesario y obligatorio tener instalado docker en la computadora o servidor que se desee iniciar este programa

**Muy importante actualizar el path de docker**

Tutorial de como instalar docker: https://www.youtube.com/watch?v=ZO4KWQfUBBc&ab_channel=FaztCode

### Instruciones

1. Abrir un powershell, bash, cmd, etc. y colocarse a la atura donde este el directorio ej: 
```bash
   cd C:\Users\mateo.ferreyra\Documents\TPO-BBDD2
```

2. Una vez en el directorio ejcutar el comando para encender los 4 diferentes contenedores:
```bash
   docker compose up --build
```
o si ese comando no funciona (generalmente seria o por tener el demon de docker apagado o por version anterior)
```bash
   docker-compose up --build
```
Si eso ya no funciona indagar sobre el error, seguro es algo del PATH del docker demon que esta funcionando mal

3. Documentacion de Swagger de FastAPI esta ubicada en http://localhost:8080/docs
