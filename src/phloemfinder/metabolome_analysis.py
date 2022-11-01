#!/usr/bin/env python3 

import os
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import seaborn as sns
import matplotlib.pyplot as plt


###################
## Class definition 
###################

class MetaboliteAnalysis:
    '''
    A class to streamline the filtering and exploration of a metabolome dataset.  
    - Offers shortcuts to perform a Principal Component Analysis on the metabolite data. 
    - Offers filtering of the metabolic dataset to remove noisy features.
    

    Parameters
    ----------
    metabolome_csv: string
        A path to a .csv file with the metabolome data (scaled or unscaled)
        Shape of the dataframe is usually (n_samples, n_features) with n_features >> n_samples
    metabolome_feature_id_col: string, default='feature_id'
        The name of the column that contains the feature identifiers.
        Feature identifiers should be unique (=not duplicated).

    Attributes
    ----------
    metabolome: dataframe
      The metabolome Pandas dataframe imported from the .csv file. 

    metabolome_validated: boolean, default=False
      Is the metabolome dataset validated?
    
    blank_features_filtered: boolean, default=False
      Are the features present in blank samples filtered out from the metabolome data?

    unreliable_features_filtered: boolean, default=False
      Are the features not reliably present within one group filtered out from the metabolome data?
    
    pca_performed: boolean, default=False
      Has PCA been performed on the metabolome data?
    
    samples_to_conditions: dataframe, default=None
      A dataframe listing the correspondence between sample ids and their experimental conditions.
      Grouping variable is often an experimental factor e.g. 'genotype'
      The second factor is an arbitrary number distinguishing the different biological replicates e.g '1'. 
      This dataframe is obtained by running the extract_samples_to_condition() method.
    
    exp_variance: dataframe with explained variance per Principal Component
      The index of the df contains the PC index (PC1, PC2, etc.)
      The second column contains the percentage of the explained variance per PC
    
    metabolome_pca_reduced: Numpy array with sample coordinates in reduced dimensions
      The dimension of the numpy array is the minimum of the number of samples and features. 




    '''
    # Class attribute shared among all instances of the class
    # By default the metabolome and phenotype data imported from .csv files will have to be validated
    # By default all filters have not been executed (blank filtering, etc.)
    metabolome_validated=False
    blank_features_filtered=False
    unreliable_features_filtered=False
    samples_to_conditions=None
    pca_performed=False

    ##########################
    # Class constructor method
    ##########################
    def __init__(
        self, 
        metabolome_csv, 
        metabolome_feature_id_col='feature_id'):
        
        # Import metabolome dataframe and verify presence of feature id column
        self.metabolome = pd.read_csv(metabolome_csv)
        if metabolome_feature_id_col not in self.metabolome.columns:
            raise ValueError("The specified column with feature identifiers {0} is not present in your '{1}' file.".format(metabolome_feature_id_col,os.path.basename(metabolome_csv)))
        else:
            self.metabolome.set_index(metabolome_feature_id_col, inplace=True)
    
    def validate_input_metabolome_df(self, metabolome_feature_id_col='feature_id'):
        '''
        Validates the dataframe containing the feature identifiers, metabolite values and sample names.
        Will place the 'feature_id_col' column as the index of the validated dataframe. 
        The validated metabolome dataframe is stored as the 'validated_metabolome' attribute 
        
        Parameters
        ----------
        metabolome_feature_id: string, default='feature_id'
            The name of the column that contains the feature identifiers.
            Feature identifiers should be unique (=not duplicated).
        
        Examples
        ----------------------------------------
        Example of a valid input metabolome dataframe


                      | genotypeA_rep1 | genotypeA_rep2 | genotypeA_rep3 | genotypeA_rep4 |
                      |----------------|----------------|----------------|----------------|
          feature_id
        | metabolite1 |   1246         | 1245           | 12345          | 12458          |
        | metabolite2 |   0            | 0              | 0              | 0              |
        | metabolite3 |   10           | 0              | 0              | 154            |
        
        '''

        if np.any(self.metabolome.values < 0):
            raise ValueError("Sorry, metabolite values have to be zero or positive integers (>=0)")
        else:
            self.metabolome_validated = True

    def extract_samples_to_condition(self, name_grouping_var='genotype', separator_replicates='_'):
        '''
        Utility function to melt (wide to long) and split grouping variable from biological replicates using specified separator

        Parameters
        ----------
        name_grouping_var: string, default='genotype'
        Name of the variable used as grouping variable.
        separator_replicates: string, default='_'
        The separator between the grouping variable and the biological replicates e.g. '_' 

        Returns
        -------
        A dataframe with the correspondence between samples and experimental condition (grouping variable)

        Example
        -------
        Input dataframe
                          | genotypeA_rep1 | genotypeA_rep2 | genotypeA_rep3 | genotypeA_rep4 |
                          |----------------|----------------|----------------|----------------|
              feature_id
            | metabolite1 |   1246         | 1245           | 12345          | 12458          |
            | metabolite2 |   0            | 0              | 0              | 0              |
            | metabolite3 |   10           | 0              | 0              | 154            |
        
        Output dataframe
            | sample_id          | genotype       | replicate      |
            |--------------------|----------------|----------------|
            | genotypeA_rep1     |   genotypeA    | rep1           |
            | genotypeA_rep2     |   genotypeA    | rep2           |
            | genotypeA_rep3     |   genotypeA    | rep3           |
            | genotypeA_rep4     |   genotypeA    | rep4           |
            | etc.
        '''
        df = self.metabolome

        melted_df = pd.melt(df.reset_index(), id_vars='feature_id', var_name="sample")
        melted_df[[name_grouping_var, 'rep']] = melted_df["sample"].str.split(pat=separator_replicates, expand=True)
        melted_df_parsed = melted_df.drop(["feature_id", "value"], axis=1)
        melted_df_parsed_dedup = melted_df_parsed.drop_duplicates()

        self.samples_to_conditions = melted_df_parsed_dedup

    #############################################
    ### Filter features detected in blank samples
    #############################################
    def discard_features_detected_in_blanks(
        self, 
        blank_sample_contains='blank'):
        '''
        Sum the abundance of each feature in the blank samples.
        Makes a list of features to be discarded (features with a positive summed abundance)
        Returns a filtered Pandas dataframe with only features not detected in blank samples

        Parameters
        ----------
        blank_sample_contains: string
            Column names with this name will be considered blank samples
        
        Returns
        -------
        A filtered Pandas dataframe without these features and with the blank samples removed. 
        '''

        if self.metabolome_validated == True:
            pass
        else:
            self.validate_input_metabolome_df()
        
        blank_cols = [col for col in self.metabolome.columns.values.tolist() if blank_sample_contains in col]

        # If the sum of a feature in blank samples is higher than 0 then 
        # this feature should be removed
        # only keep features that are not detectable in blank samples
        self.metabolome["sum_features"] = self.metabolome[blank_cols].sum(axis=1)
        self.metabolome = self.metabolome.query("sum_features == 0")
        
        # Remove columns with blank samples and the sum column used for filtering
        self.metabolome = self.metabolome.drop(blank_cols, axis=1)
        self.metabolome = self.metabolome.drop("sum_features", axis=1)    

    
    #######################################################################################
    ### Filter features that are not reliable (detected less than nb replicates in a group)
    ######################################################################################
    def filter_out_unreliable_features(
        self,
        name_grouping_var="genotype", 
        nb_times_detected=4,
        separator_replicates='_'):
        '''
        Takes a dataframe with feature identifiers in index and samples as columns
        Step 1: First melt and split the sample names to generate the grouping variable
        Step 2: count number of times a metabolite is detected in the groups. 
        If number of times detected in a group = number of biological replicates then it is considered as reliable
        Each feature receives a tag  'reliable' or 'not_reliable'
        Step 3: discard the 'not_reliable' features and keep the filtered dataframe. 

        Params
        ------
        name_grouping_var: string
            The name used when splitting between replicate and main factor e.g. "genotype" when splitting MM_rep1 into 'MM' and 'rep1'
        nb_times_detected: integer, default=4
            Number of times a metabolite should be detected to be considered 'reliable'. 
            Should be equal to the number of biological replicates for a given group of interest (e.g. genotype)
        separator_replicates: string, default="_"
            The separator to split sample names into a grouping variable (e.g. genotype) and the biological replicate number (e.g. 1)
        

        Returns
        -------
        A Pandas dataframe with only features considered as reliable, sample names and their values. 
        
        Example 
        -------
        Input dataframe

                             	| MM_1  	| MM_2  	| MM_3  	| MM_4  	| LA1330_1 	| LA1330_2 	|
                            	|----------	|----------	|----------	|----------	|----------	|----------	|
          feature_id           	 
        | rt-0.04_mz-241.88396 	| 554   	| 678   	| 674   	| 936   	| 824      	| 940      	|
        | rt-0.05_mz-143.95911 	| 1364  	| 1340  	| 1692  	| 1948  	| 1928     	| 1956     	|
        | rt-0.06_mz-124.96631 	| 0      	| 0     	| 0     	| 888   	| 786      	| 668      	|
        | rt-0.08_mz-553.45905 	| 10972 	| 11190 	| 12172 	| 11820 	| 12026    	| 11604    	|

        Output df (rt-0.06_mz-124.96631 is kicked out because 3x0 and 1x888 in MM groups)
        
                             	| MM_1  	| MM_2  	| MM_3  	| MM_4  	| LA1330_1 	| LA1330_2 	|
                            	|----------	|----------	|----------	|----------	|----------	|----------	|
          feature_id           	 
        | rt-0.04_mz-241.88396 	| 554   	| 678   	| 674   	| 936   	| 824      	| 940      	|
        | rt-0.05_mz-143.95911 	| 1364  	| 1340  	| 1692  	| 1948  	| 1928     	| 1956     	|
        | rt-0.08_mz-553.45905 	| 10972 	| 11190 	| 12172 	| 11820 	| 12026    	| 11604    	|


        '''
        df = self.metabolome

        ### Melt (required to tag reliable/not reliable features)
        melted_df = pd.melt(
            df.reset_index(), 
            id_vars='feature_id', 
            var_name="sample")
        melted_df[[name_grouping_var, 'rep']] = melted_df["sample"].str.split(pat=separator_replicates, expand=True)
        sorted_melted_df = melted_df.sort_values(by=['feature_id', name_grouping_var])
        sorted_melted_df.set_index('feature_id', inplace=True)
        sorted_melted_df_parsed = sorted_melted_df.drop('sample', axis=1)
        
        ### Identify features that are reliable
        # Creates a dictionary to have the feature identifier and a 'reliable'/'not_reliable' tag
        reliability_feature_dict = {}
        features = sorted_melted_df_parsed.index.unique().tolist()

        for feature in features:
          # Dataframe containing only one metabolite
          temp_df = sorted_melted_df_parsed.loc[feature,:]
          temp_df = temp_df.drop('rep', axis=1)

          # number of values above 0 across all groups
          min_number_of_values_above_0_across_all_groups = temp_df[temp_df['value'] > 0].groupby(by=name_grouping_var)[name_grouping_var].count().min()

          # If the feature is detected a minimum of times equal to the number of biological replicates
          # This means the feature is reliably detectable in at least one group (e.g. one genotype)
          if min_number_of_values_above_0_across_all_groups >= nb_times_detected:
            reliability_feature_dict[feature] = "reliable"    
          else:
            reliability_feature_dict[feature] = 'not_reliable'

        # Convert to a Pandas to prepare the filtering of the feature/abundance dataframe
        reliability_df = pd.DataFrame.from_dict(
            reliability_feature_dict, orient="index", columns=["reliability"]).reset_index()
        
        reliability_df = reliability_df.rename({"index":"feature_id"}, axis='columns')
        reliability_df = reliability_df[reliability_df["reliability"] == "reliable"]
        features_to_keep = reliability_df.feature_id.tolist()

        df_reliable_features = df.loc[features_to_keep,:]
                
        self.metabolome = df_reliable_features
        self.unreliable_features_filtered = True

    #################################################
    ### Write filtered metabolomoe data to a csv file
    #################################################

    def write_clean_metabolome_to_csv(self, path_of_cleaned_csv="filtered_metabolome.csv"):
        '''
        A function that verify that the metabolome dataset has been cleaned up. 
        Writes the metabolome data as a comma-separated value file on disk
        '''
        try:
            self.blank_features_filtered == True
        except:
            raise ValueError("Features in blank should be removed first using the 'discard_features_detected_in_blanks() method.")
        
        try:
            self.unreliable_features_filtered == True
        except:
            raise ValueError("Features not reliably detected within at least one group should be removed first using the 'filter_out_unreliable_features() method.") 
        
        self.metabolome.to_csv(path_or_buf=path_of_cleaned_csv, sep=',')



    #################################
    ## Principal Component Analysis
    #################################

    def compute_pca_on_metabolites(self, scale=True, n_principal_components=10, auto_transpose=True):
        """
        Performs a Principal Component Analysis on the metabolome data. 
        Assumes that number of samples < number of features/metabolites
        Performs a transpose of the metabolite dataframe if n_samples > n_features (this can be turned off with auto_transpose)
        
        Parameters
        ----------
        scale: boolean, default=True
            Perform scaling (standardize) the metabolite values to zero mean and unit variance
        n_principal_components:
            number of principal components to keep in the PCA analysis.
            if number of PCs > min(n_samples, n_features) then set to the minimum of (n_samples, n_features)
        auto_transpose: boolean, default=True
            If n_samples > n_features, performs a transpose of the feature matrix.
    
        Returns
        -------
        self: object
          .exp_variance: dataframe with explained variance per Principal Component
          .metabolome_pca_reduced: dataframe with samples in reduced dimensions
          .pca_performed: boolean set to True
        """
        # Verify that samples are in rows and features in columns
        # Usually n_samples << n_features so we should have n_rows << n_cols
        n_rows = self.metabolome.shape[0]
        n_cols = self.metabolome.shape[1]
        
        metabolite_df = self.metabolome
        if n_rows > n_cols:
            # Likely features are in row so transpose to have samples in rows
            metabolite_df = metabolite_df.transpose()
        else:
            pass
    
        if scale == True:
            scaler = StandardScaler(with_mean=True, with_std=True)
            metabolite_df_scaled = scaler.fit_transform(metabolite_df)
            metabolite_df_scaled = pd.DataFrame(metabolite_df_scaled)
            metabolite_df_scaled.columns = metabolite_df.columns
            metabolite_df_scaled.set_index(metabolite_df.index.values)       
        else:
            pass

        if n_principal_components <= np.minimum(n_rows, n_cols):
            pca = PCA(n_components=n_principal_components)
            metabolite_df_scaled_transformed = pca.fit_transform(metabolite_df_scaled)
            exp_variance = pd.DataFrame(pca.explained_variance_ratio_.round(2)*100, columns=["explained_variance"])
        # If n_principal_components > min(n_samples, n_features)
        # then n_principal_components = min(n_samples, n_features)
        else:
            n_principal_components > np.minimum(n_rows, n_cols)
            n_principal_components = np.minimum(n_rows, n_cols)
            pca = PCA(n_components=n_principal_components)
            metabolite_df_scaled_transformed = pca.fit_transform(metabolite_df_scaled)
            exp_variance = pd.DataFrame(pca.explained_variance_ratio_.round(2)*100, columns=["explained_variance"])         

        # The numbering of the components starts by default at 0. 
        # Setting this to 1 to make it more user friendly
        exp_variance.index = exp_variance.index+1
        
        # Store PCA results 
        self.exp_variance = exp_variance
        self.metabolome_pca_reduced = metabolite_df_scaled_transformed
        self.pca_performed = True

    def create_scree_plot(self, plot_file_name=None):
        '''
        Returns a barplot with the explained variance per Principal Component. 
        Has to be preceded by perform_pca()

        Parameters
        ---------
        plot_file_name: string, default='None'
          Path to a file where the plot will be saved.
          For instance 'my_scree_plot.pdf'
        '''
        try:
            self.pca_performed
        except: 
            raise AttributeError("Please compute the PCA first using the compute_pca_on_metabolites() method.") 
        
        sns.barplot(
            data=self.exp_variance, 
            x=self.exp_variance.index, 
            y="explained_variance")
        plt.xlabel("Principal Component")
        plt.ylabel("Explained variance (%)")

        # Optionally save the plot
        if plot_file_name != None:
            plot_dirname = os.path.dirname(plot_file_name)
            if plot_dirname == '': # means file will be saved in current working directory
                plt.savefig(plot_file_name)
            else:
                os.makedirs(plot_dirname, exist_ok=True)
                plt.savefig(plot_file_name)

        plt.show()


    def create_sample_score_plot(
        self, 
        name_grouping_var='genotype', 
        pc_x_axis=1, 
        pc_y_axis=2, 
        plot_file_name=None):
        '''
        Returns a sample score plot of the samples on PCx vs PCy. 
        Samples are colored based on the grouping variable (e.g. genotype) using the samples_to_condition attribute

        Parameters
        ----------
        name_grouping_var: string, default="genotype"
          Name of the variable used to color samples
          This variable has to be present in the .samples_to_condition attribute
          (see method .extract_samples_to_condition())
        pc_x_axis: integer, default=1
            Principal component on the x-axis of the scatterplot.
        pc_y_axis: integer, default=2
            Principal component on the y-axis of the scatterplot.
        plot_file_name: string, default='None'
          A file name and its path to save the sample score plot. 
          For instance "mydir/sample_score_plot.pdf"
          Path is relative to current working directory
        
        Returns
        -------
        The PCA scoreplot with samples colored by grouping variable. 
        Optionally a saved image of the plot. 
        '''
        try:
            self.pca_performed
        except: 
            raise AttributeError("Please compute the PCA first using the compute_pca_on_metabolites() method.") 

        n_features = self.metabolome.shape[0]
        n_samples = self.metabolome.shape[1]
        min_of_samples_and_features = np.minimum(n_samples, n_features)

        try:
            pc_x_axis != pc_y_axis
        except:
            raise ValueError("Values for Principal Components on x axis and y axis have to be different.")
        try: 
            pc_x_axis <= min_of_samples_and_features
        except:
            raise ValueError("Your principal component for x axis should be lower than {0}".format(min_of_samples_and_features))
        try:
            pc_y_axis <= np.minimum(n_samples, n_features)
        except:
            raise ValueError("Your principal component for y axis should be lower than {0}".format(min_of_samples_and_features))


        ### Extract grouping variable levels to color the sample dots       
        try:
            self.samples_to_conditions != None
        except:
            raise ValueError("Please run the extract_samples_to_condition() method first.")
        
        if not name_grouping_var in self.samples_to_conditions.columns:
            raise IndexError("The grouping variable '{0}' is not present in the samples_to_condition dataframe".format(name_grouping_var))
        else:
            # Build the plot
            plt.figure(figsize=(10,7))
            
            self.scatter_plot = sns.scatterplot(
            x=self.metabolome_pca_reduced[:,pc_x_axis-1],
            y=self.metabolome_pca_reduced[:,pc_y_axis-1],
            hue=self.samples_to_conditions[name_grouping_var],
            s=200)

            plt.xlabel("PC" + str(pc_x_axis) + ": " + str(self.exp_variance.iloc[pc_x_axis,0].round(2)) + "% variance") 
            plt.ylabel("PC" + str(pc_y_axis) + ": " + str(self.exp_variance.iloc[pc_y_axis,0].round(2)) + "% variance")
            plt.title("PC" + str(pc_x_axis) + " vs PC" + str(pc_y_axis))

            # Optionally save the plot
            if plot_file_name != None:
                plot_dirname = os.path.dirname(plot_file_name)
                if plot_dirname == '': # means file will be saved in current working directory
                    plt.savefig(plot_file_name)
                else:
                    os.makedirs(plot_dirname, exist_ok=True)
                    plt.savefig(plot_file_name)

            plt.show()
