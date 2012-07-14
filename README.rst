JbConsole is a management tool for Firebird RDBMS (http://www.firebirdsql.org/).

How to work
--------------

- Download jython 2.5 (http://jython.org/)

- Download Jaybird (Firebird JDBC driver ) http://www.firebirdsql.org/en/jdbc-driver/

- Set CLASSPATH to jaybird
 
  - export CLASSPATH="$CLASSPATH:/some/where/jaybird-full-2.1.6.jar"

- Fetch JbConsole

  - git clone git://github.com/nakagami/JbConsole.git

- Do command

  - jython JbConsole.py
