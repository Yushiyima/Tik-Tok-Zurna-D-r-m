from flask import Flask, request, render_template, send_file, jsonify, abort
import pandas as pd
import json
import matplotlib
matplotlib.use('Agg')  # Use the Agg backend for non-interactive plotting
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
from werkzeug.utils import safe_join
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def upload_file():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def handle_file_upload():
    if 'file' not in request.files:
        return 'No file part', 400

    file = request.files['file']
    
    if file.filename == '':
        return 'No selected file', 400

    # Read the uploaded JSON file
    data = json.load(file.stream)

    # Access the 'Activity' section
    activity_data = data.get('Activity', {})

    # Normalize the 'Video Browsing History.VideoList' data
    video_browsing_history = activity_data.get('Video Browsing History', {}).get('VideoList', [])
    if isinstance(video_browsing_history, list):
        df_video_list = pd.json_normalize(video_browsing_history)
        df_video_list['Date'] = pd.to_datetime(df_video_list['Date'])
        df_video_list['YearMonth'] = df_video_list['Date'].dt.to_period('M')
        distinct_link_counts = df_video_list.groupby('YearMonth')['Link'].nunique().reset_index(name='DistinctLinkCount')
        distinct_link_counts['MovingAvg'] = distinct_link_counts['DistinctLinkCount'].rolling(window=3).mean()

    # Normalize the 'Favorite Videos.FavoriteVideoList' data
    video_favorite_list = activity_data.get('Favorite Videos', {}).get('FavoriteVideoList', [])
    if isinstance(video_favorite_list, list):
        df_favorite_list = pd.json_normalize(video_favorite_list)
        df_favorite_list['Date'] = pd.to_datetime(df_favorite_list['Date'])
        df_favorite_list['YearMonth'] = df_favorite_list['Date'].dt.to_period('M')
        favorite_link_counts = df_favorite_list.groupby('YearMonth')['Link'].nunique().reset_index(name='DistinctFavoriteLinkCount')

    # Normalize the 'Share History.ShareHistoryList' data
    video_share_list = activity_data.get('Share History', {}).get('ShareHistoryList', [])
    if isinstance(video_share_list, list):
        df_share_list = pd.json_normalize(video_share_list)
        df_share_list['Date'] = pd.to_datetime(df_share_list['Date'])
        df_share_list['YearMonth'] = df_share_list['Date'].dt.to_period('M')
        share_link_counts = df_share_list.groupby(['YearMonth', 'Method'])['Link'].nunique().reset_index(name='DistinctShareLinkCount')

    # Normalize the 'Login History.LoginHistoryList' data
    login_history_list = activity_data.get('Login History', {}).get('LoginHistoryList', [])
    if isinstance(login_history_list, list):
        df_login_history = pd.json_normalize(login_history_list)
        df_login_history['Date'] = pd.to_datetime(df_login_history['Date'])
        df_login_history['YearMonth'] = df_login_history['Date'].dt.to_period('M')
        df_login_history['Carrier'] = df_login_history['Carrier'].replace('', 'Unknown')  # Handle empty values

    # Normalize the 'Like List.ItemFavoriteList' data
    video_like_list = activity_data.get('Like List', {}).get('ItemFavoriteList', [])
    if isinstance(video_like_list, list):
        df_like_list = pd.json_normalize(video_like_list)
        df_like_list['Date'] = pd.to_datetime(df_like_list['Date'])
        df_like_list['YearMonth'] = df_like_list['Date'].dt.to_period('M')
        like_counts = df_like_list.groupby('YearMonth').size().reset_index(name='Count')

    # Create a timestamp for the PDF file name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_path = f'Tik_Tok_Durum_{timestamp}.pdf'

    with PdfPages(pdf_path) as pdf:
        # Line Chart for Browsing History
        plt.figure(figsize=(12, 6))
        plt.plot(distinct_link_counts['YearMonth'].astype(str), distinct_link_counts['DistinctLinkCount'], marker='o', label='Distinct Link Count (Browsing)', color='blue')
        plt.plot(distinct_link_counts['YearMonth'].astype(str), distinct_link_counts['MovingAvg'], marker='x', color='orange', label='3-Month Moving Average')

        for line in plt.gca().lines:
            xdata, ydata = line.get_data()
            for i in range(len(xdata)):
                plt.annotate(f'{ydata[i]:.0f}', (xdata[i], ydata[i]), textcoords="offset points", xytext=(0, 5), ha='center')

        plt.title('Distinct Count of Links from Video Browsing History by Year-Month')
        plt.xlabel('Year-Month')
        plt.ylabel('Distinct Count of Links')
        plt.xticks(rotation=45)
        plt.grid()
        plt.legend()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Bar Chart for Favorite Videos
        plt.figure(figsize=(12, 6))
        bars = plt.bar(favorite_link_counts['YearMonth'].astype(str), favorite_link_counts['DistinctFavoriteLinkCount'], label='Distinct Favorite Link Count', color='green', alpha=0.6)
        for bar in bars:
            bar_height = bar.get_height()
            if bar_height > 0:
                plt.annotate(f'{bar_height}', xy=(bar.get_x() + bar.get_width() / 2, bar_height),
                             xytext=(0, 3), textcoords='offset points', ha='center', va='bottom')

        plt.title('Distinct Count of Links from Favorite Videos by Year-Month')
        plt.xlabel('Year-Month')
        plt.ylabel('Distinct Count of Links')
        plt.xticks(rotation=45)
        plt.grid()
        plt.legend()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Bar Chart for Share History
        plt.figure(figsize=(12, 6))
        share_counts = share_link_counts.pivot(index='YearMonth', columns='Method', values='DistinctShareLinkCount').fillna(0)
        ax = share_counts.plot(kind='bar', figsize=(12, 6))
        for patch in ax.patches:
            ax.annotate(f'{int(patch.get_height())}', (patch.get_x() + patch.get_width() / 2, patch.get_height()),
                        textcoords="offset points", xytext=(0, 5), ha='center')

        plt.title('Distinct Count of Links from Share History by Year-Month and Method')
        plt.xlabel('Year-Month')
        plt.ylabel('Distinct Count of Links')
        plt.xticks(rotation=45)
        plt.grid()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Bar Chart for Network Type
        network_counts = df_login_history['Carrier'].value_counts().reset_index()
        network_counts.columns = ['NetworkType', 'Count']
        plt.figure(figsize=(12, 6))
        ax = network_counts.plot(kind='bar', x='NetworkType', y='Count', legend=False)
        plt.title('Count of Logins by Network Type')
        plt.xlabel('Network Type')
        plt.ylabel('Count')
        for patch in ax.patches:
            ax.annotate(f'{int(patch.get_height())}', (patch.get_x() + patch.get_width() / 2, patch.get_height()),
                        textcoords="offset points", xytext=(0, 5), ha='center')
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Line Chart for Monthly Login Counts
        monthly_login_counts = df_login_history.groupby('YearMonth').size().reset_index(name='Count')
        plt.figure(figsize=(12, 6))
        ax = monthly_login_counts.plot(kind='line', x='YearMonth', y='Count', marker='o')
        for i, value in enumerate(monthly_login_counts['Count']):
            ax.annotate(f'{value}', (i, value), textcoords="offset points", xytext=(0, 5), ha='center')
        plt.title('Monthly Login Counts')
        plt.xlabel('Year-Month')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.grid()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Line Chart for Like Counts
        plt.figure(figsize=(12, 6))
        plt.plot(like_counts['YearMonth'].astype(str), like_counts['Count'], marker='o', color='purple', label='Like Count')

        for i, value in enumerate(like_counts['Count']):
            plt.annotate(f'{value}', (i, value), textcoords="offset points", xytext=(0, 5), ha='center')

        plt.title('Monthly Like Counts')
        plt.xlabel('Year-Month')
        plt.ylabel('Count of Likes')
        plt.xticks(rotation=45)
        plt.grid()
        plt.legend()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # Pie Chart for Carrier counts
        carrier_counts = df_login_history['Carrier'].value_counts()
        plt.figure(figsize=(8, 8))
        plt.pie(carrier_counts, labels=carrier_counts.index, autopct='%1.1f%%', startangle=90)
        plt.title('Login Counts by Carrier')
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        pdf.savefig()
        plt.close()

        # Summary table
        summary_data = [
        ['Total Count of Links', df_video_list['Link'].count() if 'df_video_list' in locals() else 0],
        ['Total Count of Favorite Videos', df_favorite_list['Link'].count() if 'df_favorite_list' in locals() else 0],
        ['Total Count of Shares', df_share_list['Link'].count() if 'df_share_list' in locals() else 0],
        ['Total Login Counts', df_login_history.shape[0] if 'df_login_history' in locals() else 0],
        ['Total Like Counts', like_counts['Count'].sum() if 'like_counts' in locals() else 0],
        ]

        # Create the summary table
        plt.figure(figsize=(8, 4))
        plt.axis('tight')
        plt.axis('off')
        plt.table(cellText=summary_data, colLabels=['Description', 'Value'], cellLoc='center', loc='center')
        plt.title('Summary Table')
        pdf.savefig()
        plt.close()

    return send_file(pdf_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)

