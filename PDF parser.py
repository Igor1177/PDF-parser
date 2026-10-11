#PDF PARSER BY IVTIIbd-22
import pypdf

file_reader = input("Название начально файла (в конце.pdf): ")
start = int(input("Начальная страница: "))
finish = int(input("Конечная страница: "))
name_file = input("Название файла (в конце.pdf): ")

reader = pypdf.PdfReader(file_reader)
writer = pypdf.PdfWriter()
for i in range(start, finish+1):
    writer.add_page(reader.pages[i])
writer.write(name_file)
print(f"Создание файла {name_file} прошло успешно")
