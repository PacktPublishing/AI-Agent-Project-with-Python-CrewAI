import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import PDFSearchTool

# If you want to run a snippet of code before or after the crew starts, 
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

PDF_PATH = 'C:\\Users\\user\\Downloads\\Documents\\sample_document.pdf'

@CrewBase
class BuddyAi():
	"""BuddyAi crew"""

	# Learn more about YAML configuration files here:
	# Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
	# Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
	agents_config = 'config/agents.yaml'
	tasks_config = 'config/tasks.yaml'

	# If you would like to add tools to your agents, you can learn more about it here:
	# https://docs.crewai.com/concepts/agents#agent-tools
	@agent
	def pdf_reader(self) -> Agent:
		return Agent(
			config=self.agents_config['pdf_reader'],
			verbose=False,
			tools=[PDFSearchTool(pdf=PDF_PATH)]
		)
	
	@agent
	def summarizer(self) -> Agent:
		return Agent(
			config=self.agents_config['summarizer'],
			verbose=False
		)
	
	@agent
	def quiz_maker(self) -> Agent:
		return Agent(
			config=self.agents_config['quiz_maker'],
			verbose=False,
			strict_parser=False
		)
	
	@agent
	def study_buddy(self) -> Agent:
		return Agent(
			config=self.agents_config['study_buddy'],
			verbose=False,
		)

	@agent
	def flashcard_maker(self) -> Agent:
		return Agent(
			config=self.agents_config['flashcard_maker'],
			verbose=False,
			strict_parser=False,
			function_calling_llm=None
		)

	# To learn more about structured task outputs, 
	# task dependencies, and task callbacks, check out the documentation:
	# https://docs.crewai.com/concepts/tasks#overview-of-a-task
	@task
	def reading_task(self) -> Task:
		"""
			This task will:
			- verify file existence and access
			- attempt multiple queries to extract full content
			- Return extracted content or clear out all error messages
		"""
		def reading_logic(agent, inputs):
			# 0. verify the file path and acces
			if not os.path.isfile(PDF_PATH):
				return "ERROR: PDF file not found or not accessible at the given path."
			
			# 1. Attempt to retrieve content from the PDF using different queries.
			queries = ["", "all content", "document", "*"]
			extracted_content = None
			fallback_snippet = "PDF RAG the PDFSearchTool is designed to search PDF files."

			for q in queries:
				agent.think(f"Trying query '{q}' to get PDF content. ")
				result = agent.use_tool("Search a PDF's content", {"query": q})
				if result and fallback_snippet not in result:
					# trying to get something different from the fallback description
					extracted_content = result.strip()
					break
				
			# 2. confirm that content was extracted
			if not extracted_content:
				return (
					"ERROR: unable to extract meaningful text from the PDF."
					"Make sure that PDF has searchable text or try another document."
				)

			return extracted_content

		return Task(
			config=self.tasks_config['reading_task'],
			logic=reading_logic
		)
	
	@task
	def summarizing_task(self) -> Task:
		"""
			Summarize the extracted PDF text.
				If the reading_task returned an ERROR,
					handle that gracefully here!
		"""
		def summarizing_logic(agent, inputs, context):
			pdf_text = context.get('reading_task', '')
			if pdf_text.startswith("ERROR:"):
				return f"Cannot summarize because: {pdf_text}"
			
			return agent.llm(
				f"Summarize the following text into a concise overview:\n\n{pdf_text}"
			).strip

		return Task(
			config=self.tasks_config['summarizing_task'],
			logic=summarizing_logic,
			output_file='output/summary.md'
		)
	
	@task
	def quiz_task(self) -> Task:
		return Task(
			config=self.tasks_config['quiz_task'],
		)

	@task
	def user_test_task(self) -> Task:
		def test_logic(agent, inputs, context):
			quiz_text = context.get('quiz_task', '')

			# the agent will prompt the user:
			agent.think("I will now ask the user to answer the quiz.")
			agent.say("Here are your quiz questions:\n")
			agent.say(quiz_text)
			agent.say("Please provide your answers in the format: A,B,C,... for each question in order.")

			user_answers = inputs.get('human_input')

			user_answers_list = [ans.strip().upper() for ans in user_answers.split(",")]

			# Q1, A, b, c, Correct answer: A

			import re
			correct_answers = re.findall(r'Correct Answer:\s*([A-D])', quiz_text, re.IGNORECASE)

			score = 0
			for user_ans, correct_ans in zip(user_answers_list, correct_answers):
				if user_ans == correct_ans.upper():
					score += 1

			total = len(correct_ans)
			result = f"You answered {score} out of {total} correctly!"

			agent.say(result)
			return result
			

		return Task(
			config=self.tasks_config['user_test_task'],
			logic=test_logic
		)

	@task
	def flashcard_task(self) -> Task:
		return Task(
			config=self.tasks_config['flashcard_task']
		)

	@task
	def study_flashcards_task(self) -> Task:
		def study_logic(agent, inputs, context):
			# parse the flashcards from the flashcard_task output
			# let the user type show, flip or quit to navigate them.
			flashcards_text = context.get('flashcards_task', '')
			if not flashcards_text.strip():
				return "No flashcards found. Possibly an error."
			
			agent.think("Parsing flashcards from text...")

			# 1) front: ...
			#    back: ...
			lines = [l.strip() for l in flashcards_text.split('\n') if l.strip()]

			flashcards = []
			current_fc = {}

			for line in lines:
				if line.lower().startswith("front:"):
					current_fc = {"front": line[6:].strip(), "back": ""}
				elif line.lower().startswith("back:"):
					current_fc["back"] = line[5:].strip()
					flashcards.append(current_fc)
					current_fc = {}

			if not flashcards:
				return "Couldn't parse any flashcards from the text."
			
			agent.say(f"I have {len(flashcards)} flashcards loaded. We'll go through them now.\n")
			agent.say("Type 'show' to see the next flashcard, 'flip' to see its back, or 'quit' to end.\n")

			index = 0
			showing_front = False
			user_input = inputs.get('human_input', '').lower()

			if user_input == "quit":
				return "Exiting flashcard study session."
			
			if index >= len(flashcards):
				return "No more flashcards left."
			
			if user_input == "show":
				agent.say(f"Flashcard {index + 1} front: {flashcards[index]['front']}")
				showing_front = True
				return "Type 'flip' next time to see the back, or 'quit' to stop."
			elif user_input == "flip" and not showing_front:
				return "You need to 'show' the card first. Then you can 'flip' it."
			elif user_input == "flip" and showing_front:
				# show the back
				agent.say(f"Flashcard {index+1} back: {flashcards[index]['back']}")
				return f"Now you can type 'show' to move to the next card or 'quit' to stop."
			else:
				return "Invalid command. Please type 'show' or 'flip' or 'quit'"


		return Task(
			config=self.tasks_config['study_flashcards_task'],
			logic=study_logic,
			human_input=True
		)

	@crew
	def crew(self) -> Crew:
		"""Creates the BuddyAi crew"""
		# To learn how to add knowledge sources to your crew, check out the documentation:
		# https://docs.crewai.com/concepts/knowledge#what-is-knowledge

		return Crew(
			agents=self.agents, # Automatically created by the @agent decorator
			tasks=self.tasks, # Automatically created by the @task decorator
			process=Process.sequential,
			verbose=True,
			# process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
		)
