import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from typing import Optional, List, Dict
from dotenv import load_dotenv
import os

load_dotenv()

def get_snowflake_connection():
    """
    Create and return a Snowflake connection
    
    Returns:
        snowflake.connector.connection object
    """
    try:
        conn = snowflake.connector.connect(
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            role=os.getenv('SNOWFLAKE_ROLE')
        )
        print("Successfully connected to Snowflake")
        return conn
    except Exception as e:
        print(f"Error connecting to Snowflake: {e}")
        raise

def query_snowflake(
    sql: str, 
    conn: Optional[snowflake.connector.SnowflakeConnection] = None
) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a pandas DataFrame
    
    Args:
        sql: SQL query string
        conn: Optional Snowflake connection object. If None, creates a new connection.
        
    Returns:
        pandas DataFrame with query results
    """
    # Create connection if not provided
    if conn is None:
        conn = get_snowflake_connection()
        print('Successfully connected to Snowflake')
    try:
        cur = conn.cursor()
        print('Executing query...')
        cur.execute(sql)
        df = cur.fetch_pandas_all()
        print(f'Query successful. Returning {len(df)} rows.')
        return df
    finally:
        cur.close()


def write_to_snowflake(
    df: pd.DataFrame,
    table_name: str,
    database: str = None,
    schema: str = None,
    conn: Optional[snowflake.connector.SnowflakeConnection] = None,
    if_exists: str = 'append',
    auto_create_table: bool = False,  # Changed default to False
    overwrite: bool = False,
    validate_columns: bool = True  # New parameter
) -> int:
    """
    Write a pandas DataFrame to Snowflake table
    
    Args:
        df: pandas DataFrame to write
        table_name: Name of the target table
        database: Optional database name (uses connection default if None)
        schema: Optional schema name (uses connection default if None)
        conn: Optional Snowflake connection. If None, creates a new connection.
        if_exists: What to do if table exists: 'append', 'replace', or 'fail'
        auto_create_table: Whether to auto-create the table if it doesn't exist
        overwrite: If True, truncates table before inserting
        
    Returns:
        Number of rows written
    """
    # Create connection if not provided
    should_close = False
    if conn is None:
        conn = get_snowflake_connection()
        should_close = True
    
    try:
        # Set database and schema if provided
        cursor = conn.cursor()
        if database:
            cursor.execute(f"USE DATABASE {database}")
        if schema:
            cursor.execute(f"USE SCHEMA {schema}")
        cursor.close()
        
        # Handle overwrite
        if overwrite and if_exists == 'append':
            cursor = conn.cursor()
            cursor.execute(f"TRUNCATE TABLE IF EXISTS {table_name}")
            cursor.close()
            print(f"Truncated table {table_name}")
        
        # Write data using pandas tools
        success, nchunks, nrows, _ = write_pandas(
            conn=conn,
            df=df,
            table_name=table_name.upper(),  # Snowflake converts to uppercase
            auto_create_table=auto_create_table,
            overwrite=(if_exists == 'replace')
        )
        
        if success:
            print(f"Successfully wrote {nrows} rows to {table_name} in {nchunks} chunks")
            return nrows
        else:
            print(f"Failed to write to {table_name}")
            return 0
            
    finally:
        if should_close:
            conn.close()


def upsert_to_snowflake(
    df: pd.DataFrame,
    table_name: str,
    key_columns: List[str],
    database: str = None,
    schema: str = None,
    conn: Optional[snowflake.connector.SnowflakeConnection] = None
) -> int:
    """
    Upsert (insert or update) data to Snowflake using MERGE statement
    
    Args:
        df: pandas DataFrame to upsert
        table_name: Name of the target table
        key_columns: List of column names to use as unique keys for matching
        database: Optional database name
        schema: Optional schema name
        conn: Optional Snowflake connection
        
    Returns:
        Number of rows affected
    """
    # Create connection if not provided
    should_close = False
    if conn is None:
        conn = get_snowflake_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        
        # Set database and schema if provided
        if database:
            cursor.execute(f"USE DATABASE {database}")
        if schema:
            cursor.execute(f"USE SCHEMA {schema}")
        
        # Create temporary table name
        temp_table = f"{table_name}_TEMP_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
        
        # Write to temporary table
        print(f"Writing to temporary table {temp_table}...")
        write_pandas(
            conn=conn,
            df=df,
            table_name=temp_table.upper(),
            auto_create_table=True,
            overwrite=True
        )
        
        # Build column lists for MERGE
        all_columns = df.columns.tolist()
        non_key_columns = [col for col in all_columns if col not in key_columns]
        
        # Build match condition
        match_conditions = " AND ".join([f"target.{col} = source.{col}" for col in key_columns])
        
        # Build update SET clause
        update_sets = ", ".join([f"{col} = source.{col}" for col in non_key_columns])
        
        # Build insert columns and values
        insert_columns = ", ".join(all_columns)
        insert_values = ", ".join([f"source.{col}" for col in all_columns])
        
        # Execute MERGE
        merge_sql = f"""
        MERGE INTO {table_name.upper()} AS target
        USING {temp_table.upper()} AS source
        ON {match_conditions}
        WHEN MATCHED THEN
            UPDATE SET {update_sets}
        WHEN NOT MATCHED THEN
            INSERT ({insert_columns})
            VALUES ({insert_values})
        """
        
        print(f"Executing MERGE statement...")
        cursor.execute(merge_sql)
        rows_affected = cursor.rowcount
        
        # Drop temporary table
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table.upper()}")
        
        cursor.close()
        print(f"Upsert complete. {rows_affected} rows affected.")
        
        return rows_affected
        
    finally:
        if should_close:
            conn.close()


def validate_columns_exist(
    conn: snowflake.connector.SnowflakeConnection,
    table_name: str,
    df_columns: List[str],
    database: str = None,
    schema: str = None
) -> tuple[bool, List[str], List[str]]:
    """
    Validate that DataFrame columns exist in the target table
    
    Args:
        conn: Snowflake connection
        table_name: Name of the target table
        df_columns: List of column names from DataFrame
        database: Optional database name
        schema: Optional schema name
        
    Returns:
        Tuple of (all_valid, valid_columns, missing_columns)
    """
    cursor = conn.cursor()
    
    try:
        # Get table columns
        if database and schema:
            query = f"SHOW COLUMNS IN TABLE {database}.{schema}.{table_name}"
        elif schema:
            query = f"SHOW COLUMNS IN TABLE {schema}.{table_name}"
        else:
            query = f"SHOW COLUMNS IN TABLE {table_name}"
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        # Extract column names (case-insensitive)
        table_columns = {row[2].upper() for row in result}  # row[2] is column name
        
        # Check which DataFrame columns exist in table
        valid_columns = []
        missing_columns = []
        
        for col in df_columns:
            if col.upper() in table_columns:
                valid_columns.append(col)
            else:
                missing_columns.append(col)
        
        all_valid = len(missing_columns) == 0
        
        return all_valid, valid_columns, missing_columns
        
    finally:
        cursor.close()


def execute_sql(
    sql: str,
    conn: Optional[snowflake.connector.SnowflakeConnection] = None
) -> int:
    """
    Execute a SQL statement (INSERT, UPDATE, DELETE, etc.)
    
    Args:
        sql: SQL statement to execute
        conn: Optional Snowflake connection
        
    Returns:
        Number of rows affected
    """
    # Create connection if not provided
    should_close = False
    if conn is None:
        conn = get_snowflake_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows_affected = cursor.rowcount
        cursor.close()
        
        print(f"SQL executed successfully. {rows_affected} rows affected.")
        return rows_affected
        
    finally:
        if should_close:
            conn.close()