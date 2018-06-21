from datetime import date, timedelta
import numpy as np
import pandas as pd
import time, pprint    

from sklearn.metrics import mean_squared_error
pp = pprint.PrettyPrinter(indent=3)

def get_week_labels(n_weeks, year, month, day):
    """
        Function to get the week labels
        n_weeks  : number of weeks, integer
    """
    week_labels = []
    for n_week in range(n_weeks+1):
        week_labels.append(int((date(year, month, day) - timedelta(days=7*(n_week))).strftime('%Y%m%d')))
    
    return week_labels[::-1]

def convert_date(row, column, nan_value='NaT'):
    """
        Function to convert string date to integer and hour in seconds
        column  : name of columns, string
        row     : dataframe row
    """
    if row[column] != nan_value:
        temp = row[column].split()
        hour = temp[1].split(':')
        date = temp[0].split('-')
        hour_int = int(hour[0]) * 3600 + int(hour[1]) * 60 + int(hour[2])
        date_int = int(date[0]) * 10000 + int(date[1]) * 100 + int(date[2])
    else:
        hour_int = np.nan
        date_int = np.nan
        
    return pd.Series([date_int * 1.0, hour_int * 1.0])

def convert_int(row, column, nan_value='-'):
    """
        Function to convert string time to seconds
        column  : name of columns, string
        row     : dataframe row
    """
    if row[column] != nan_value:    
        H = True if 'H' in row[column] else False
        M = True if 'M' in row[column] else False

        time = row[column].replace('H', ' ').replace('M', ' ').split()
        if H and M:
            days = int(time[0]) * 3600 + int(time[1]) * 60 + int(time[2])
        elif H and not M:
            days = int(time[0]) * 3600 + int(time[1]) * 60
        elif not H and M:
            days = int(time[0]) * 60 + int(time[1])
        else:
            days = int(time[0])
    else:
        days = np.nan
        
    return days * 1.0

def make_set(train, test, fill_method='median', date_field='Fecha_Ejec_Inicio_Int', int_field='duracion_int', order_field='Fecha_Ejec_Inicio_Int', ascending=True):
    """
        This function make a val data set that contains dates in train and test
        We use a fill method to get the execution time for a job that execute more than one
        time in a Id_Malla for a specific date
        
        train          : DataFrame, train dataframe
        test           : DataFrame, test datafram
        fill_method    : String, median or mean
        date_field     : String, a valid date in integer
        int_field      : String, the field should be fill in val dataset
        ascending      : Boolean, 
    """
    
    val = {}
    
    if fill_method == 'mean':
        temp_group = train.loc[train.Mxrc == 0].groupby([date_field, 'Id_Job', 'Id_Malla']).mean().reset_index()
    elif fill_method == 'median':
        temp_group = train.loc[train.Mxrc == 0].groupby([date_field, 'Id_Job', 'Id_Malla']).median().reset_index()
    else:
        print('Error: fill_method should be mean or median')
        return null
    
    date = sorted(train[date_field].unique())[0]
    # This code fill [Id_Job, Id_Malla] in val. We set as 1 in Time field
    for ix, row in test.iterrows():
        val[(date, row['Id_Job'], row['Id_Malla'])] = 0
    
    for ix, row in temp_group.sort_values([order_field, int_field], ascending=ascending).iterrows():
        # val[(date, row['Id_Job'], row['Id_Malla'])] = [row[int_field], row['Mxrc'], row['Maxcmpc']]
        val[(date, row['Id_Job'], row['Id_Malla'])] = row[int_field]
        
    val = pd.DataFrame(pd.Series(val)).reset_index()
    val.columns = ['Fecha_Ejec_Inicio_Int', 'Id_Job', 'Id_Malla', int_field]
    # val[int_field], val['Mxrc'], val['Maxcmpc'] = zip(*val['temp'])
    # del val['temp']
    return val

def apply_cats(df, cat_cols):
    """
        Changes any columns of strings in df (DataFrame) into categorical variables.
    """
    for n, c in df.items():
        if (n in cat_cols) and (df[n].dtype.name=='object'):
            df[n] = pd.Categorical(c, categories=df[n].astype('category').cat.categories, ordered=True)           
            
def date_diff(d1, d2):
    """
        Days between d1 and d2, expressed as integers
    """
    return (date(int(d1) // 10000, (int(d1) // 100) % 100, int(d1) % 100) - \
            date(int(d2) // 10000, (int(d2) // 100) % 100, int(d2) % 100)).days
    
def days_since(day_df, all_data, keys, nan_date=20170701):
    """
        Get number of days between last *keys* and day_df date
    """
    last_operations = all_data.drop_duplicates(keys, keep='first') \
            .set_index(keys)['Fecha_Ejec_Inicio_Int'].copy().to_dict()
    return day_df.apply(lambda r: date_diff(r['Fecha_Ejec_Inicio_Int'],
            last_operations.get(tuple(r[k] for k in keys) if len(keys) > 1 else r[keys[0]],
            nan_date)), axis=1)

# Count without considering weekdays
def add_date_diffs(day_df, all_data):
    """
        Adds datediffs features to a dataset
    """
    all_data = all_data[all_data.Mxrc == 0]
    date = sorted(day_df['Fecha_Ejec_Inicio_Int'].unique())[0]
    all_data = all_data.sort_values('Fecha_Ejec_Inicio_Int', ascending=False)
    
    day_df['DaysSinceMainframeOp'] = days_since(day_df, all_data.loc[all_data['Fecha_Ejec_Inicio_Int'] < date].reset_index(), ['Id_Job', 'Id_Malla'])

def days_count(day_df, all_data, keys):
    """
        Get frequency *keys* in historical trades before day_df
    """
    day_counter = all_data.groupby(keys).size().to_dict()
    return day_df.apply(lambda r: \
            day_counter.get(tuple(r[k] for k in keys) if len(keys) > 1 else r[keys[0]], 
            0), axis=1)
    
def add_days_count(day_df, all_data):
    """
        Adds dayscount features to a dataset (representing a single day/week)
        from the information of trades
    """
    all_data = all_data[all_data.Mxrc == 0]
    date = sorted(day_df['Fecha_Ejec_Inicio_Int'].unique())[0]
    
    day_df['DaysCountMainframeOp'] = days_count(day_df, all_data.loc[all_data['Fecha_Ejec_Inicio_Int'] < date].reset_index(), ['Id_Job', 'Id_Malla'])

def get_day(row_date):
    if np.isnan(row_date):
        return np.nan
    else:
        day = int(row_date % 100)
        month = int(int(row_date / 100) % 100)
        year = int(row_date / 10000)
        return date(year, month, day).weekday()
    
def add_date_features(day_df):
    day_df['DiaSemana'] = day_df.apply(lambda row: get_day(row['Fecha_Ejec_Inicio_Int']), axis=1)

def add_mean_days(df, all_data, start_date):
    
    date_df = sorted(df['Fecha_Ejec_Inicio_Int'].unique())[0]
    number_day = get_day(date_df)
    
    temp = all_data.loc[(all_data['Fecha_Ejec_Inicio_Int'] >= start_date) &\
                        (all_data['Fecha_Ejec_Inicio_Int'] < date_df) &\
                        (all_data['DiaSemana'] == number_day) & (all_data['Mxrc'] == 0)]\
                        .groupby(['Id_Job', 'Id_Malla']).median().reset_index()
    dict_temp = {}
    for ix, row in temp.iterrows():
        dict_temp[(row['Id_Job'], row['Id_Malla'])] = row['duracion_int']
    
    df['promedio_por_dia'] = 0
    for ix, row in df.iterrows():
        if (row['Id_Job'], row['Id_Malla']) in dict_temp:
            df.at[ix, 'promedio_por_dia'] = dict_temp[(row['Id_Job'], row['Id_Malla'])]

def add_mean_weeks(df, all_data, start_date):
    date_df = sorted(df['Fecha_Ejec_Inicio_Int'].unique())[0]
    temp = all_data.loc[(all_data['Fecha_Ejec_Inicio_Int'] >= start_date) &\
                        (all_data['Fecha_Ejec_Inicio_Int'] < date_df) &\
                        (all_data['Mxrc'] == 0)]\
                        .groupby(['Id_Job', 'Id_Malla']).median().reset_index()       
    dict_temp = {}
    for ix, row in temp.iterrows():
        dict_temp[(row['Id_Job'], row['Id_Malla'])] = row['duracion_int']
    
    df['promedio_por_semana'] = 0
    for ix, row in df.iterrows():
        if (row['Id_Job'], row['Id_Malla']) in dict_temp:
            df.at[ix, 'promedio_por_semana'] = dict_temp[(row['Id_Job'], row['Id_Malla'])]

def add_mean_features(df, all_data, n_week):
    temp_date = sorted(df.Fecha_Ejec_Inicio_Int.unique())[0]
    day = int(temp_date % 100)
    month = int(int(temp_date / 100) % 100)
    year = int(temp_date / 10000)
    start_date = int((date(year, month, day) - timedelta(days=7*(n_week))).strftime('%Y%m%d'))
    
    add_mean_days(df, all_data, start_date)
    add_mean_weeks(df, all_data, start_date)
    
def fit_model(model, X_trn, y_trn, X_val, y_val, early_stopping, cat_indices):
    if X_val is not None:
        early_stopping = 30 if early_stopping else 0
        model.fit(X_trn, y_trn, 
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=early_stopping,
                eval_metric='mse')
    else:
        model.fit(X_trn, y_trn)
        
def calculate_metrics(model, metrics, X_trn, y_trn, X_val, y_val):
    metric_function = {'mse': mean_squared_error}
    dset = {'trn': {'X': X_trn, 'y': y_trn},
            'val': {'X': X_val, 'y': y_val}}
    
    for d in dset:
        if dset[d]['X'] is not None:
            y_pred = model.predict(dset[d]['X'])
            for m in metrics:
                metrics[m][d] += [metric_function[m](dset[d]['y'], y_pred)]
        else:
            for m in metrics:
                metrics[m][d] += [0] # no val set
                
    pp.pprint(metrics)
    print()
    
def run_model(model, X_train, y_train, X_val, y_val, X_test, 
              metric_names, results=None, params_desc='',
              early_stopping=False, cat_indices=None):
    if results is None: results = pd.DataFrame()
    metrics = {metric: {'trn': [], 'val': []} for metric in metric_names}
    y_test = np.zeros((len(X_test)))
    start = time.time()
    
    fit_model(model, X_train, y_train, X_val, y_val, early_stopping, cat_indices)
    calculate_metrics(model, metrics, X_train, y_train, X_val, y_val)
    y_test = model.predict(X_test)
            
    end = time.time()
    means = {f'{d}_{m}_mean': np.mean(metrics[m][d]) for m in metrics \
                                                     for d in metrics[m]}
    metadata = {'params': params_desc, 'time': round(end - start, 2)}
    pp.pprint(means)
    results = results.append(pd.Series({**metadata, **means}),
                             ignore_index=True)
    return y_test, metrics, results, model