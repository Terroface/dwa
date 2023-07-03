
"""
This module generates a base Cube.js schema file from a dictionary containing table and column 
information from a data warehouse. The file specifies the SQL source, joins, dimensions, and 
measures for each table, utilizing cardinality information inferred from earlier steps, as well 
as custom field descriptions. This aids in the setup of a Cube.js analytics layer by automating 
the schema generation based on the underlying data structure and relationships.

"""

import os

# Convert a string to camel case
def to_camel_case(name):
    components = name.split('_')
    return components[0].lower() + ''.join(x.title() for x in components[1:])


def generate_cube_js_base_file(
    schema,
    file_path,
    field_descriptions_dictionary,
    inferred_join_cardinalities,
    semantics_from_large_language_model,
    concise_table_names,
    table_pks,
    ):

    # Create the necessary directories
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Open the file for writing
    with open(file_path, 'w') as file:

        print(f"Attempting to generate base Cube file here: {file_path}")

        # Write the import statement at the top of the file
        file.write('import { databaseSchema, databaseName } from \'../tablePrefix\';\n\n')

        # Iterate over each table in the dictionary
        for table_name, columns in schema.items():

            # Write the cube-level attributes
            table_name_camel_case = to_camel_case(table_name)
            file.write(f'cube(`{table_name_camel_case}_base`, {{\n\n')

            file.write(f'  sql: `select * from ${{databaseName()}}.${{databaseSchema()}}."{table_name}"`,\n\n')

            file.write('  shown: false,\n\n')

            # Write joins if they exist
            if inferred_join_cardinalities:
                file.write('  joins: {\n')
                for join in inferred_join_cardinalities:
                    if join['left_table'] == table_name or join['right_table'] == table_name:
                        join_table_name = join['right_table'] if join['left_table'] == table_name else join['left_table']
                        join_table_name_camel_case = to_camel_case(join_table_name)
                        relationship = join['cardinality']
                        reverse_relationship = join['reverse_cardinality']
                        file.write(f'    {join_table_name_camel_case}: {{\n')
                        if join['left_table'] == table_name:
                            file.write(f'      relationship: "{relationship}",\n')
                            file.write(f'      sql: `${{CUBE}}."{join["left_column"]}" = "{join_table_name.lower()}"."{join["right_column"]}"`\n')
                        else:
                            file.write(f'      relationship: "{reverse_relationship}",\n')
                            file.write(f'      sql: `${{CUBE}}."{join["right_column"]}" = "{join_table_name.lower()}"."{join["left_column"]}"`\n')
                        file.write('    },\n')
                file.write('  },\n')

            # Initialize dimensions and measures
            dimensions = []
            measures = []

            # Process each column in the table
            for column_info in columns:
                column_name = column_info['column_name']
                data_type = column_info['data_type']
                column_name_camel_case = to_camel_case(column_name)
                column_description = field_descriptions_dictionary.get(column_name.lower(), 'no description') # Find field description 

                # Check if semantics are specified in semantics_from_large_language_model
                column_semantics_from_llm = semantics_from_large_language_model.get(table_name, {}).get(column_name, {})
                is_key_column_from_llm = column_semantics_from_llm.get('is_key_column', None)
                measure_1_type_from_llm = column_semantics_from_llm.get('measure_1_type', None)

                # Prep column's attributes based on LLM semantics if exist, otherwise hardcoded rules

                # Primary Key
                if column_name.lower().endswith('_pk'):
                    type_to_print = 'string'
                    shown_value = 'false'
                    dimensions.append(f'{column_name_camel_case}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}",\n      primaryKey: true,\n      shown: {shown_value}\n    }}')
                
                # Foreign Key
                elif column_name.lower().endswith('_fk'):
                    type_to_print = 'string'
                    shown_value = 'false'
                    dimensions.append(f'{column_name_camel_case}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}",\n      shown: {shown_value}\n    }}')
                
                # String types
                elif data_type.lower() in ['text', 'varchar', 'string', 'char', 'binary', 'variant']:
                    type_to_print = 'string'
                    # If the column is a key column according to the LLM, hide it
                    if is_key_column_from_llm == 'true':
                        shown_value = 'false'
                    else:
                        shown_value = 'true'
                    dimensions.append(f'{column_name_camel_case}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}",\n      shown: {shown_value} \n  }}')
                
                # Numeric types
                elif data_type.lower() in ['number', 'numeric', 'float', 'float64', 'integer', 'int', 'smallint', 'bigint']:
                    # If a measure 1 type is specified in the LLM, use it
                    if measure_1_type_from_llm is not None: 
                        type_to_print = measure_1_type_from_llm
                    else:
                        type_to_print = 'sum'
                    # If the column is a key column according to the LLM, hide it
                    if is_key_column_from_llm == 'true':
                        shown_value = 'false'
                    else:
                        shown_value = 'true'
                    measures.append(f'{to_camel_case("sum_" + column_name)}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}",\n      shown: {shown_value} \n   }}')
                
                # Date, time and timestamp-related types
                elif data_type.lower() in ['timestamp', 'timestamp_tz', 'timestamp_ltz', 'timestamp_ntz', 'date', 'time']:
                    type_to_print = 'time'
                    dimensions.append(f'{column_name_camel_case}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}" \n    }}')
                
                # Boolean types
                elif data_type.lower() in ['boolean']:
                    type_to_print = 'boolean'
                    dimensions.append(f'{column_name_camel_case}: {{\n      sql: `${{CUBE}}."{column_name}"`,\n      description: `{column_description}`, \n      type: "{type_to_print}" \n    }}')

            # Write dimensions
            file.write('  dimensions: {\n\n')
            file.write(',\n\n'.join('    ' + dim for dim in dimensions))
            file.write('\n\n  },\n\n')

            # Write measures
            file.write('  measures: {\n\n')
            file.write(',\n\n'.join('    ' + measure for measure in measures))
            if measures: # Add a comma before the count if there are other measures
                file.write(',\n\n')
            # Final measure is always the count
            file.write(f'    {to_camel_case("count_" + concise_table_names[table_name])}: {{\n      type: "count_distinct",\n      sql:`${{CUBE}}."{table_pks[table_name][0]}"`\n    }}\n\n  }}\n')

            # Write the end of the cube
            file.write('});\n\n')
    
    print(f"Base Cube file generated")