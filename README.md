# Simulación BYOD (Bring Your Own Device) usando Road Warrior VPN SSL

## Descripción

Se ha desarrollado un sistema cliente-servidor mediante el uso de sockets SSL. Este sistema cuenta con un mecanismo de registro de usuarios, a los que solo se les pide un nombre de usuario y contraseña. Estos dos campos son almacenados en una base de datos, la cual asegura la integridad de la información restringiendo el acceso a los datos y estableciendo un procedimiento concreto para poder acceder a ellos. También se permite a los usuarios iniciar sesión introduciendo su nombre de usuario y contraseña, siendo verificada la existencia de estos dos campos en la base de datos.

Todas las interacciones del usuario con el sistema se realizan mediante un Pop-up de cliente. A su vez, todas las interacciones entre el sistema cliente y el servidor están protegidas mediante el uso del protocolo TLS 1.3 (NIST-SP-800-52r2), ya que este implementa los requisitos de autenticidad,confidencialidad e integridad.

El cliente podrá enviar mensajes introduciendo los en texto plano al Pop-up siempre y cuando estos sean menores de 144 caracteres. Por cada sesión el sistema guardará en una base de datos qué usuario se ha conectado, en qué fecha, y el número de mensajes enviados. Si un usuario se conectase 2 veces dentro del mismo día en la base de datos solo habría una entrada con la suma del total de mensajes de las 2 sesiones.

Además, se han prevenido los ataques de suplantación de identidad, en los que un atacante podría hacerse pasar por el servidor. Esto se ha llevado a cabo usando un certificado que verifica que el servidor es realmente el servidor y no un atacante. Como medida de seguridad aparte este certificado junto con su clave secreta se han almacenado y encriptado en un archivo llamado keystore.p12. En la carpeta de información adicional se muestra como se ha generado este archivo repitiendo el proceso con una contraseña de prueba.


### IMPORTANTE

El script en python create_keystore que se encuentra en la raíz del proyecto es información sensible, ya que contiene la contraseña con la que se cifrará el keystore y por tanto no debería en ningún caso ser público. 

Ese script además no funcionará sin el certificado y la clave del servidor, y se encuentra ahí sólo para mostrar como se ha creado el archivo keystore.p12 que se encuentra en resources, debido a que este es un proyecto puramente educativo.


## Instalación

### 1. Entorno virtual
#### 1.1 Crear el entorno virtual
```bash
python3 -m venv venv
```
#### Activar el entorno virtual
En linux: 
```bash
source venv/bin/activate  
```
O en Windows: 

```bash
venv\Scripts\activate
```

#### 1.2 Instalar dependencias del entorno virtual
```bash
pip install -r requirements.txt
```

### 2. Configurar MariaDB
#### 2.1 En Ubuntu
```bash
sudo apt install mariadb-server -y
sudo systemctl start mariadb
sudo mysql_secure_installation
```
Valores a introducir tras ejecutar el comando `mysql_secure_installation`:
```bash
- Enter current password for root (enter for none): (enter)
- Switch to unix_socket authentication [Y/n]: `y`
- Change the root password? [Y/n]: `y`
    - New password: <tu_contraseña_de_root>
    - Re-enter new password: <tu_contraseña_de_root>
- Remove anonymous users? [Y/n]: `y`
- Disallow root login remotely? [Y/n]: `y` 
- Remove test database and access to it? [Y/n]: `y`
- Reload privilege tables now? [Y/n] : `y`
```
A continuación, para continuar con la creación de la base de datos:
```bash
sudo mariadb -u root -p
```
Usar la contraseña de root que se ha configurado anteriormente. Una vez dentro de la consola de MariaDB, para crear las bases de datos ejecutar el siguiente comando:
```sql
source resources/database.sql;
```

#### 2.2 En Windows
Descargar MariaDB de la página oficial y configurar el superusuario root durante la instalación. A continuación, abrir una terminal en el directorio base del proyecto (mideporte) y ejecutar el siguiente comando:
```bash
mariadb -u root -p
```
Nota: Si no se reconoce el comando `mariadb`, añadir la ruta de instalación de MariaDB al PATH del sistema.

(Opcional pero recomendable) Si se desea realizar una instalación segura igual que en Ubuntu, ejecutar las siguientes sentencias SQL:
```sql
DELETE FROM mysql.user WHERE User='';
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
FLUSH PRIVILEGES;
```	
Para crear las bases de datos, ejecutar el siguiente comando:
```sql
source resources/database.sql;
```


## INICIO DEL SISTEMA

Antes de iniciar el sistema será necesario introducir en el .env del sistema la contraseña del servidor de la siguiente manera:

KEYSTORE_PASSWORD="KegJpxUCW8c6^mK%%roscJULLw7SgwS3FCVFb!CZopcGGQJaLM%Qra9PNmD@eexm" 

Para poner en marcha el sistema lo primero que hay que hacer es encender los 2 servidores, para ello primero se debe ejecutar el contenido del script .sql para preparar la base de datos en MariaDB. Luego se debe abrir una carpeta en la carpeta raíz del proyecto y ejecutar:

```bash
python ./src/servers/server.py 
python ./src/servers/salt_server.py
```

Para ejecutar el cliente, abrir una terminal en la carpeta raíz y ejecutar:
```bash
python ./src/client/client_socket.py
```

Aunque se proporcione el código fuente, se recomienda configurar las variables de entorno al gusto del usuario y que se creen ejecutables por mayor seguridad.
